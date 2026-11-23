"""Aprire applicazioni, link e ricerche."""
import configparser
import difflib
import subprocess
import urllib.parse
from pathlib import Path

from . import tool

DIRS = [Path.home() / ".local/share/applications", Path("/usr/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local/share/flatpak/exports/share/applications"]

ALIASES = {
    "chrome": "google chrome", "google": "google chrome", "browser": "google chrome",
    "terminale": "konsole", "terminal": "konsole", "file": "dolphin", "cartelle": "dolphin",
    "esplora file": "dolphin", "impostazioni": "impostazioni di sistema",
    "calcolatrice": "kcalc", "musica": "spotify", "editor": "kate",
}


def scan_apps():
    apps = {}
    for d in DIRS:
        if not d.is_dir():
            continue
        for f in d.glob("*.desktop"):
            if f.stem in apps:
                continue
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                cp.read(f, encoding="utf-8")
                e = cp["Desktop Entry"]
            except Exception:
                continue
            if e.get("Type") != "Application" or e.get("NoDisplay", "").lower() == "true":
                continue
            names = [e.get("Name[it]", ""), e.get("Name", ""), e.get("GenericName[it]", ""),
                     e.get("GenericName", ""), e.get("Keywords[it]", ""), e.get("Keywords", ""), f.stem]
            apps[f.stem] = {"id": f.stem, "name": e.get("Name[it]") or e.get("Name", f.stem),
                            "search": " ".join(n.lower() for n in names if n)}
    return apps


def find_app(query):
    q = ALIASES.get(query.lower().strip(), query.lower().strip())
    best, best_score = None, 0.0
    for a in scan_apps().values():
        name = a["name"].lower()
        if q == name:
            score = 100
        elif name.startswith(q):
            score = 85
        elif q in name:
            score = 75
        elif q in a["search"]:
            score = 55
        else:
            score = difflib.SequenceMatcher(None, q, name).ratio() * 60
        if score > best_score:
            best, best_score = a, score
    return best if best_score >= 40 else None


@tool("open_app", "Apre un'applicazione installata sul PC (es. Chrome, Dolphin, Spotify, Konsole, Steam).",
      {"name": {"type": "string", "description": "nome dell'app"}}, ["name"])
def open_app(ctx, name):
    app = find_app(name)
    if not app:
        return f"Non ho trovato nessuna app chiamata '{name}'."
    ctx.step("🚀", f"Apro {app['name']}")
    subprocess.Popen(["gtk-launch", app["id"]], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return f"Ho aperto {app['name']}."


@tool("open_url", "Apre un sito web nel browser.",
      {"url": {"type": "string", "description": "indirizzo, es. youtube.com"}}, ["url"])
def open_url(ctx, url):
    if "://" not in url:
        url = "https://" + url
    ctx.step("🌐", f"Apro {url}")
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return f"Ho aperto {url}."


@tool("web_search", "Cerca qualcosa su Google aprendo il browser.",
      {"query": {"type": "string"}}, ["query"])
def web_search(ctx, query):
    ctx.step("🔎", f"Cerco: {query}")
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return f"Ho cercato '{query}' su Google."


@tool("open_folder", "Apre una cartella nel file manager.",
      {"path": {"type": "string", "description": "es. ~/Scaricati"}}, ["path"])
def open_folder(ctx, path):
    p = Path(path).expanduser()
    if not p.exists():
        return f"La cartella {p} non esiste."
    ctx.step("📂", f"Apro {p}")
    subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return f"Ho aperto {p}."
