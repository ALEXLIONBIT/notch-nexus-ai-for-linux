"""Vedere lo schermo: screenshot (Spectacle, va su KDE Wayland) + OCR tesseract + visione."""
import csv
import difflib
import io
import subprocess
import time

from . import tool, ToolResult
from ..config import CACHE


def screenshot():
    path = CACHE / "screen.png"
    path.unlink(missing_ok=True)
    subprocess.run(["spectacle", "-b", "-n", "-f", "-o", str(path)], timeout=20,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if path.exists() and path.stat().st_size > 0:
            break
        time.sleep(0.1)
    if not path.exists():
        raise RuntimeError("screenshot non riuscito")
    return path


def small_copy(path, max_w=1280):
    for old in CACHE.glob("screen_small_*.jpg"):     # file unico per ogni screenshot
        old.unlink(missing_ok=True)
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)))
    out = CACHE / f"screen_small_{int(time.time() * 1000)}.jpg"
    img.save(out, quality=85)
    return out


def _langs():
    try:
        out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
        have = [l.strip() for l in out.splitlines()[1:]]
        sel = [l for l in ("ita", "eng") if l in have]
        return ["-l", "+".join(sel)] if sel else []
    except FileNotFoundError:
        return []


def ocr(path):
    """Ritorna righe [{text, x, y, w, h, words:[...]}] in pixel dello screenshot."""
    out = subprocess.run(["tesseract", str(path), "stdout", *_langs(), "tsv"],
                         capture_output=True, text=True, timeout=60).stdout
    lines = {}
    for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        txt = (r.get("text") or "").strip()
        if not txt or float(r.get("conf") or -1) < 40:
            continue
        key = (r["page_num"], r["block_num"], r["par_num"], r["line_num"])
        w = {"text": txt, "x": int(r["left"]), "y": int(r["top"]), "w": int(r["width"]),
             "h": int(r["height"])}
        lines.setdefault(key, []).append(w)
    res = []
    for words in lines.values():
        x0 = min(w["x"] for w in words); y0 = min(w["y"] for w in words)
        x1 = max(w["x"] + w["w"] for w in words); y1 = max(w["y"] + w["h"] for w in words)
        res.append({"text": " ".join(w["text"] for w in words), "x": x0, "y": y0,
                    "w": x1 - x0, "h": y1 - y0, "words": words})
    res.sort(key=lambda l: (l["y"] // 15, l["x"]))
    return res


def find_text(lines, target):
    """Trova la posizione (centro) del testo più simile a target."""
    t = target.lower().strip()
    best, score = None, 0.0
    for l in lines:
        ws = l["words"]
        for i in range(len(ws)):
            for j in range(i, min(i + 6, len(ws))):
                span = " ".join(w["text"] for w in ws[i:j + 1]).lower()
                s = difflib.SequenceMatcher(None, t, span).ratio()
                if s > score:
                    x0 = ws[i]["x"]; x1 = ws[j]["x"] + ws[j]["w"]
                    y0 = min(w["y"] for w in ws[i:j + 1]); y1 = max(w["y"] + w["h"] for w in ws[i:j + 1])
                    best, score = ((x0 + x1) // 2, (y0 + y1) // 2, span), s
    return (best, score) if score >= 0.6 else (None, score)


@tool("look_screen", "Guarda lo schermo dell'utente: fa uno screenshot, legge il testo (OCR) e "
      "ti mostra l'immagine. Usalo quando l'utente chiede cosa c'è sullo schermo o per capire dove cliccare.",
      {"question": {"type": "string", "description": "cosa cercare o capire"}})
def look_screen(ctx, question=""):
    ctx.step("📸", "Guardo lo schermo")
    shot = screenshot()
    small = small_copy(shot)
    ctx.image(str(small))
    ctx.step("🔤", "Leggo il testo (OCR)")
    from PIL import Image
    w, h = Image.open(shot).size
    from . import inputs
    inputs._size = (w, h)
    lines = ocr(shot)
    # testo + posizione del centro in coordinate 0-1000 (le stesse del tool click)
    out = []
    for l in lines:
        cx = int((l["x"] + l["w"] / 2) / w * 1000)
        cy = int((l["y"] + l["h"] / 2) / h * 1000)
        out.append(f"[{cx},{cy}] {l['text']}")
    text = "\n".join(out)[:2200]
    return ToolResult("Testo sullo schermo con posizione [x,y] in coordinate 0-1000:\n"
                      f"{text or '(nessun testo)'}", image=str(small))


@tool("read_screen_text", "Legge solo il testo visibile sullo schermo con l'OCR (più veloce di look_screen).")
def read_screen_text(ctx):
    ctx.step("🔤", "Leggo il testo sullo schermo")
    lines = ocr(screenshot())
    return "\n".join(l["text"] for l in lines)[:4000] or "(nessun testo)"
