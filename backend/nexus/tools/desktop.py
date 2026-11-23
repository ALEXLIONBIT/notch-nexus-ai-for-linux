"""Riordinare il desktop (con conferma e annulla) e leggere file."""
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from . import tool
from .. import osys
from ..config import DATA

UNDO_FILE = DATA / "undo_desktop.json"

CATEGORIES = {
    "Immagini": {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "heic", "avif"},
    "PDF": {"pdf"},
    "Documenti": {"doc", "docx", "odt", "txt", "rtf", "md", "xls", "xlsx", "ods", "ppt", "pptx",
                  "odp", "csv", "epub"},
    "Video": {"mp4", "mkv", "avi", "mov", "webm"},
    "Audio": {"mp3", "wav", "flac", "ogg", "m4a", "opus"},
    "Archivi": {"zip", "rar", "7z", "tar", "gz", "xz", "bz2", "zst"},
    "Immagini disco": {"iso", "img"},
    "Codice": {"py", "js", "ts", "html", "css", "sh", "json", "c", "cpp", "h", "java", "rs", "go"},
    "Programmi": {"appimage", "deb", "rpm", "exe", "msi", "flatpakref", "msix", "appx"},
}


def desktop_dir():
    return osys.desktop_dir()


def category(p: Path):
    ext = p.suffix.lower().lstrip(".")
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Altro"


def unique(dst: Path):
    if not dst.exists():
        return dst
    i = 2
    while True:
        cand = dst.with_name(f"{dst.stem} ({i}){dst.suffix}")
        if not cand.exists():
            return cand
        i += 1


@tool("organize_desktop", "Riordina il desktop spostando i file sparsi in cartelle per tipo "
      "(Immagini, PDF, Documenti, Video, Archivi...). Chiede conferma all'utente da solo.")
def organize_desktop(ctx):
    d = desktop_dir()
    files = [p for p in d.iterdir()
             if p.is_file() and not p.name.startswith(".") and p.suffix.lower() not in (".desktop", ".lnk", ".url", ".ini")]
    if not files:
        return "Il desktop è già in ordine: non ci sono file sparsi."
    plan = [(p, category(p)) for p in files]
    counts = Counter(c for _, c in plan)
    summary = ", ".join(f"{n} in {c}" for c, n in counts.most_common())
    ctx.step("🧹", f"Piano: {summary}")
    if not ctx.confirm(f"Sposto {len(files)} file in {len(counts)} cartelle. Procedo?"):
        return "L'utente ha annullato il riordino."
    moves = []
    for p, cat in plan:
        target_dir = d / cat
        target_dir.mkdir(exist_ok=True)
        dst = unique(target_dir / p.name)
        shutil.move(str(p), dst)
        moves.append({"src": str(p), "dst": str(dst)})
    UNDO_FILE.write_text(json.dumps({"time": time.time(), "moves": moves}, ensure_ascii=False), encoding="utf-8")
    ctx.step("✅", f"Spostati {len(moves)} file")
    return f"Fatto: ho spostato {len(moves)} file ({summary}). Si può annullare."


@tool("undo_organize", "Annulla l'ultimo riordino del desktop rimettendo i file al loro posto.")
def undo_organize(ctx):
    if not UNDO_FILE.exists():
        return "Non c'è nessun riordino da annullare."
    data = json.loads(UNDO_FILE.read_text(encoding="utf-8"))
    back = 0
    for m in reversed(data["moves"]):
        src, dst = Path(m["src"]), Path(m["dst"])
        if dst.exists() and not src.exists():
            shutil.move(str(dst), src)
            back += 1
            try:
                dst.parent.rmdir()  # solo se vuota
            except OSError:
                pass
    UNDO_FILE.unlink()
    ctx.step("↩️", f"Rimessi a posto {back} file")
    return f"Ho rimesso a posto {back} file."


@tool("list_files", "Elenca i file in una cartella.",
      {"path": {"type": "string", "description": "cartella, es. ~/Scaricati. Vuoto = desktop"}})
def list_files(ctx, path=""):
    p = Path(path).expanduser() if path else desktop_dir()
    if not p.is_dir():
        return f"{p} non è una cartella."
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    names = [i.name + ("/" if i.is_dir() else "") for i in items if not i.name.startswith(".")]
    ctx.step("📂", f"Guardo {p}")
    return f"{p} contiene {len(names)} elementi: " + ", ".join(names[:80])


@tool("read_text_file", "Legge un file di testo.", {"path": {"type": "string"}}, ["path"])
def read_text_file(ctx, path):
    p = Path(path).expanduser()
    ctx.step("📄", f"Leggo {p.name}")
    return p.read_text(encoding="utf-8", errors="replace")[:4000]
