"""Aprire applicazioni, link e ricerche."""
import configparser
import difflib
import json
import os
import subprocess
import time
import urllib.parse
from pathlib import Path

from . import tool
from ..osys import IS_WIN, run, popen, open_path

DIRS = [Path.home() / ".local/share/applications", Path("/usr/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local/share/flatpak/exports/share/applications"]

ALIASES = {
    "chrome": "google chrome", "google": "google chrome", "browser": "google chrome",
    "terminale": "konsole", "terminal": "konsole", "file": "dolphin", "cartelle": "dolphin",
    "esplora file": "dolphin", "impostazioni": "impostazioni di sistema",
    "calcolatrice": "kcalc", "musica": "spotify", "editor": "kate",
}


if IS_WIN:
    ALIASES = {
        "chrome": "google chrome", "google": "google chrome", "browser": "microsoft edge", "edge": "microsoft edge",
        "terminale": "terminale", "terminal": "terminale", "powershell": "windows powershell",
        "prompt": "prompt dei comandi", "cmd": "prompt dei comandi", "file": "esplora file",
        "cartelle": "esplora file", "esplora risorse": "esplora file", "explorer": "esplora file",
        "impostazioni": "impostazioni", "calcolatrice": "calcolatrice", "musica": "spotify",
        "editor": "blocco note", "notepad": "blocco note", "word": "word", "excel": "excel",
        "paint": "paint", "store": "microsoft store", "negozio": "microsoft store",
    }

_win_cache = {"t": 0.0, "apps": {}}


def _win_scan():
    """App di Windows: collegamenti del menu Start (.lnk) + app dello Store (Get-StartApps). Tenute 2 minuti."""
    if time.time() - _win_cache["t"] < 120 and _win_cache["apps"]:
        return _win_cache["apps"]
    apps = {}
    roots = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs"]
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*.lnk"):
            low = f.stem.lower()
            if any(w in low for w in ("uninstall", "disinstalla", "readme", "leggimi", "help", "guida")):
                continue
            apps.setdefault(low, {"id": str(f), "name": f.stem, "search": f"{low} {f.parent.name.lower()}"})
    try:
        out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                   "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
                  capture_output=True, text=True, encoding="utf-8", timeout=30).stdout.strip()
        items = json.loads(out) if out else []
        for it in items if isinstance(items, list) else [items]:
            name, appid = it.get("Name") or "", it.get("AppID") or ""
            if name and appid and name.lower() not in apps:
                apps[name.lower()] = {"id": "shell:AppsFolder\\" + appid, "name": name, "search": name.lower()}
    except Exception as e:
        print("Get-StartApps non disponibile:", e)
    _win_cache.update(t=time.time(), apps=apps)
    return apps


def launch_app(app):
    """Avvia un'app trovata con find_app."""
    if IS_WIN:
        if app["id"].startswith("shell:AppsFolder"):
            popen(["explorer.exe", app["id"]])
        else:
            open_path(app["id"])
    else:
        popen(["gtk-launch", app["id"]])


def scan_apps():
    if IS_WIN:
        return _win_scan()
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


def _win_browsers():
    """Browser registrati in Windows: {chiave: {id, name, exe}}."""
    import winreg
    found = {}
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            root = winreg.OpenKey(hive, r"SOFTWARE\Clients\StartMenuInternet")
        except OSError:
            continue
        i = 0
        while True:
            try:
                key = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, key) as k:
                    name = winreg.QueryValue(k, None) or key
                with winreg.OpenKey(root, key + r"\shell\open\command") as k:
                    exe = winreg.QueryValue(k, None).strip()
            except OSError:
                continue
            exe = exe.split('"')[1] if exe.startswith('"') else exe.split(" ")[0]
            found.setdefault(key, {"id": key, "name": name, "exe": exe})
    return found


def list_browsers():
    """Browser installati: [{id, name}] (un solo elemento per nome)."""
    if IS_WIN:
        try:
            return sorted(({"id": b["id"], "name": b["name"]} for b in _win_browsers().values()),
                          key=lambda b: b["name"].lower())
        except Exception:
            return []
    found = {}
    for d in DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                cp.read(f, encoding="utf-8")
                e = cp["Desktop Entry"]
            except Exception:
                continue
            if e.get("Type") != "Application" or e.get("NoDisplay", "").lower() == "true":
                continue
            mime, cats = e.get("MimeType", ""), e.get("Categories", "")
            if "x-scheme-handler/http" not in mime and not ("WebBrowser" in cats and "Settings" not in cats):
                continue
            name = e.get("Name", f.stem)
            if f.stem.endswith(".settings") or "settings" in name.lower() or "impostazioni" in name.lower():
                continue
            if name not in found or "x-scheme-handler/http" in mime:
                found[name] = {"id": f.stem, "name": name}
    return sorted(found.values(), key=lambda b: b["name"].lower())


def open_in_browser(ctx, url):
    """Apre l'url nel browser scelto nelle impostazioni (o in quello di sistema)."""
    b = ctx.cfg.get("browser") or ""
    if IS_WIN:
        exe = _win_browsers().get(b, {}).get("exe") if b else None
        popen([exe, url]) if exe else open_path(url)
        return
    cmd = ["gtk-launch", b, url] if b else ["xdg-open", url]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def find_app(query, cfg=None):
    raw = query.lower().strip()
    if raw in ("browser", "internet", "il browser") and cfg and cfg.get("browser") and IS_WIN:
        name = _win_browsers().get(cfg["browser"], {}).get("name", "")
        raw = name.lower() or raw
    elif raw in ("browser", "internet", "il browser") and cfg and cfg.get("browser"):
        for a in scan_apps().values():
            if a["id"] == cfg["browser"]:
                return a
    q = ALIASES.get(raw, raw)
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


@tool("open_app", "Apre un'applicazione installata sul PC (es. Chrome, "
      + ("Esplora file, Spotify, Blocco note, Steam)." if IS_WIN else "Dolphin, Spotify, Konsole, Steam)."),
      {"name": {"type": "string", "description": "nome dell'app"}}, ["name"])
def open_app(ctx, name):
    app = find_app(name, ctx.cfg)
    if not app:
        return f"Non ho trovato nessuna app chiamata '{name}'."
    ctx.step("🚀", f"Apro {app['name']}")
    launch_app(app)
    return f"Ho aperto {app['name']}."


@tool("open_url", "Apre un sito web nel browser.",
      {"url": {"type": "string", "description": "indirizzo, es. youtube.com"}}, ["url"])
def open_url(ctx, url):
    if "://" not in url:
        url = "https://" + url
    ctx.step("🌐", f"Apro {url}")
    open_in_browser(ctx, url)
    return f"Ho aperto {url}."


@tool("web_search", "Cerca qualcosa su Google aprendo il browser.",
      {"query": {"type": "string"}}, ["query"])
def web_search(ctx, query):
    ctx.step("🔎", f"Cerco: {query}")
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    open_in_browser(ctx, url)
    return f"Ho cercato '{query}' su Google."


@tool("open_folder", "Apre una cartella nel file manager.",
      {"path": {"type": "string", "description": "es. ~/Scaricati" + (", ~/Downloads, C:/Users" if IS_WIN else "")}}, ["path"])
def open_folder(ctx, path):
    p = Path(path).expanduser()
    if not p.exists():
        return f"La cartella {p} non esiste."
    ctx.step("📂", f"Apro {p}")
    open_path(p)
    return f"Ho aperto {p}."
