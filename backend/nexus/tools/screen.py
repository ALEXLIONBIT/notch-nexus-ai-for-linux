"""Vedere lo schermo: screenshot (Spectacle, va su KDE Wayland) + OCR tesseract + visione."""
import csv
import os
import difflib
import io
import subprocess
import time

from . import tool, ToolResult
from ..config import CACHE
from ..osys import IS_WIN, run


def _wait_file(path, tries=50):
    for _ in range(tries):
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.1)
    return False


def screenshot():
    """Screenshot dell'intero schermo. KDE: Spectacle; wlroots: grim; GNOME/Cinnamon/MATE: gnome-screenshot;
    X11 in generale e Windows: Pillow (ImageGrab, schermo principale)."""
    import shutil
    path = CACHE / "screen.png"
    path.unlink(missing_ok=True)
    if not IS_WIN:
        from ..osys import fix_gui_env
        fix_gui_env()                                # servizio partito prima della sessione: senza display Spectacle muore
    if IS_WIN:
        from . import _win_input  # noqa: F401  (pixel veri anche con lo schermo scalato)
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
        return path
    tries = []
    if shutil.which("spectacle"):
        tries.append(["spectacle", "-b", "-n", "-f", "-o", str(path)])
    if shutil.which("grim") and os.environ.get("WAYLAND_DISPLAY"):
        tries.append(["grim", str(path)])
    if shutil.which("gnome-screenshot"):
        tries.append(["gnome-screenshot", "-f", str(path)])
    for cmd in tries:
        try:
            subprocess.run(cmd, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError):
            continue
        if _wait_file(path, 30):
            return path
    if os.environ.get("DISPLAY"):                    # X11 (es. Linux Mint Cinnamon)
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
        return path
    if not tries:
        raise RuntimeError("manca il programma per gli screenshot: installa spectacle, grim o gnome-screenshot")
    raise RuntimeError("lo screenshot non è riuscito (il programma " + tries[0][0] + " non vede lo schermo): "
                       "riprova tra un attimo o riavvia NEXUS da Personalizza → Aggiornamenti → Riavvia")


def small_copy(path, max_w=1024):
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
        out = run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
        have = [l.strip() for l in out.splitlines()[1:]]
        sel = [l for l in ("ita", "eng") if l in have]
        return ["-l", "+".join(sel)] if sel else []
    except FileNotFoundError:
        return []


def _ocr_band(img_path, langs):
    env = dict(os.environ, OMP_THREAD_LIMIT="1")      # un thread per striscia: le strisce vanno in parallelo
    out = run(["tesseract", str(img_path), "stdout", *langs, "--psm", "11", "tsv"],
              capture_output=True, text=True, timeout=60, env=env).stdout
    words = []
    for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        txt = (r.get("text") or "").strip()
        if not txt or float(r.get("conf") or -1) < 40:
            continue
        words.append({"text": txt, "x": int(r["left"]), "y": int(r["top"]), "w": int(r["width"]),
                      "h": int(r["height"]), "line": (r["block_num"], r["par_num"], r["line_num"])})
    return words


def _ocr_windows(path):
    """OCR integrato in Windows 10/11 (Windows.Media.Ocr): niente da installare, usa le lingue di Windows."""
    import asyncio
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile
    from PIL import Image

    img = Image.open(path)
    scale = 1.0
    limit = int(OcrEngine.max_image_dimension or 2600)
    src = path
    if max(img.size) > limit:                         # immagine troppo grande per l'OCR di Windows
        scale = limit / max(img.size)
        src = CACHE / "ocr_win.png"
        img.resize((int(img.width * scale), int(img.height * scale))).save(src)

    async def go():
        f = await StorageFile.get_file_from_path_async(str(src.resolve()))
        stream = await f.open_async(FileAccessMode.READ)
        bmp = await (await BitmapDecoder.create_async(stream)).get_software_bitmap_async()
        if bmp.bitmap_pixel_format != BitmapPixelFormat.BGRA8:
            bmp = SoftwareBitmap.convert(bmp, BitmapPixelFormat.BGRA8)
        eng = None
        for tag in ("it", "it-IT", "en-US"):
            lang = Language(tag)
            if OcrEngine.is_language_supported(lang):
                eng = OcrEngine.try_create_from_language(lang)
                break
        eng = eng or OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            raise RuntimeError("nessuna lingua OCR installata in Windows")
        return await eng.recognize_async(bmp)

    res = asyncio.run(go())
    out = []
    for line in res.lines:
        words = []
        for w in line.words:
            r = w.bounding_rect
            words.append({"text": w.text, "x": int(r.x / scale), "y": int(r.y / scale),
                          "w": int(r.width / scale), "h": int(r.height / scale)})
        if not words:
            continue
        x0 = min(w["x"] for w in words); y0 = min(w["y"] for w in words)
        x1 = max(w["x"] + w["w"] for w in words); y1 = max(w["y"] + w["h"] for w in words)
        out.append({"text": " ".join(w["text"] for w in words), "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                    "words": words})
    out.sort(key=lambda l: (l["y"] // 15, l["x"]))
    return out


def ocr(path, bands=8):
    """Testo sullo schermo: [{text, x, y, w, h, words}] in pixel dello screenshot.
    Veloce: metà risoluzione e 8 strisce lette in parallelo. Su Windows usa l'OCR di sistema."""
    if IS_WIN:
        import shutil
        try:
            return _ocr_windows(path)
        except Exception as e:
            if not shutil.which("tesseract"):
                raise RuntimeError(f"OCR non disponibile: {e}") from e
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    img = Image.open(path).convert("L")
    scale = 2 if img.width > 2000 else 1
    if scale > 1:
        img = img.resize((img.width // scale, img.height // scale))
    langs = _langs()
    h, overlap = img.height, 30
    step = h // bands
    jobs = []
    for i in range(bands):
        y0 = max(0, i * step - overlap)
        y1 = h if i == bands - 1 else min(h, (i + 1) * step + overlap)
        band = CACHE / f"ocr_band{i}.png"
        img.crop((0, y0, img.width, y1)).save(band)
        jobs.append((band, y0))
    with ThreadPoolExecutor(bands) as ex:
        results = list(ex.map(lambda j: (_ocr_band(j[0], langs), j[1]), jobs))
    lines, seen = {}, set()
    for bi, (words, y0) in enumerate(results):
        for w in words:
            x, y = w["x"] * scale, (w["y"] + y0) * scale
            key = (w["text"], round(x / 20), round(y / 20))       # stessa parola nella sovrapposizione
            if key in seen:
                continue
            seen.add(key)
            ww = {"text": w["text"], "x": x, "y": y, "w": w["w"] * scale, "h": w["h"] * scale}
            lines.setdefault((bi,) + w["line"], []).append(ww)
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


@tool("look_screen", "Guarda lo schermo: fa uno screenshot e te lo mostra. Per cliccare usa le coordinate "
      "0-1000 dell'immagine (click) oppure click_text per una scritta. Metti read_text=true solo se ti serve "
      "leggere tanto testo preciso (è più lento).",
      {"question": {"type": "string", "description": "cosa cercare o capire"},
       "read_text": {"type": "boolean", "description": "leggi anche il testo con l'OCR (lento)"}})
def look_screen(ctx, question="", read_text=False):
    ctx.step("📸", "Guardo lo schermo")
    shot = screenshot()
    small = small_copy(shot)
    ctx.image(str(small))
    from PIL import Image
    w, h = Image.open(shot).size
    from . import inputs
    inputs._size = (w, h)
    if not read_text:
        return ToolResult("Ecco lo schermo (immagine allegata). Coordinate per click: 0-1000.", image=str(small))
    ctx.step("🔤", "Leggo il testo (OCR)")
    out = []
    for l in ocr(shot):
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
