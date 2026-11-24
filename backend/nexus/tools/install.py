"""Trovare e installare programmi (Flatpak su Linux, winget su Windows, senza password) e giochi Steam."""
import difflib
import json
import shutil
import subprocess
import urllib.parse
import urllib.request

import re

from . import tool
from .apps import find_app
from ..osys import IS_WIN, run, open_path


def _winget_search(name):
    """[(id, nome)] da winget (il catalogo ufficiale di Windows)."""
    out = run(["winget", "search", name, "--source", "winget", "--accept-source-agreements",
               "--disable-interactivity"], capture_output=True, text=True, encoding="utf-8",
              errors="replace", timeout=90).stdout
    lines = [l.rstrip() for l in re.split(r"[\r\n]+", out)]
    for i, l in enumerate(lines):
        if re.fullmatch(r"-{10,}", l.strip()) and i > 0:
            head = lines[i - 1].split("\x08")[-1]
            starts = [m.start() for m in re.finditer(r"\S+", head)]
            # l'intestazione può avere spinner davanti: si allinea all'inizio della prima parola
            off = starts[0]
            starts = [x - off for x in starts]
            rows = []
            for row in lines[i + 1:]:
                if len(starts) < 2 or len(row) < starts[1]:
                    continue
                nm = row[:starts[1]].strip()
                pid = row[starts[1]:starts[2] if len(starts) > 2 else None].split()[0] if row[starts[1]:].split() else ""
                if nm and pid and not pid.endswith("…"):      # id troncati: non installabili
                    rows.append((pid, nm))
            return rows
    return []


def _winget_install(ctx, name):
    import shutil
    if not shutil.which("winget"):
        return "winget non c'è su questo PC: aggiorna 'Programma di installazione app' dal Microsoft Store."
    ctx.step("🔍", f"Cerco {name} con winget")
    rows = _winget_search(name)
    if not rows:
        return f"Non ho trovato '{name}' nel catalogo winget."
    names = [r[1] for r in rows]
    best = difflib.get_close_matches(name, names, n=1, cutoff=0.0)
    pid, app_name = rows[names.index(best[0])] if best else rows[0]
    if not ctx.confirm(f"Installo {app_name} con winget?"):
        return "L'utente non ha voluto installarlo."
    ctx.step("⬇️", f"Installo {app_name} (può volerci qualche minuto)")
    r = run(["winget", "install", "-e", "--id", pid, "--silent", "--accept-package-agreements",
             "--accept-source-agreements", "--disable-interactivity"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1800)
    if r.returncode != 0:
        return f"Installazione non riuscita: {(r.stdout or r.stderr)[-300:]}"
    from . import apps
    apps._win_cache["t"] = 0                         # rilegge il menu Start
    return f"Ho installato {app_name}. Puoi aprirlo con open_app."


def _flatpak_installed():
    if IS_WIN or not shutil.which("flatpak"):
        return []
    out = subprocess.run(["flatpak", "list", "--app", "--columns=application,name"],
                         capture_output=True, text=True, timeout=20).stdout
    return [l.split("\t") for l in out.splitlines() if "\t" in l]


@tool("check_app", "Controlla se un programma è installato sul PC (es. Steam, Spotify, OBS).",
      {"name": {"type": "string"}}, ["name"])
def check_app(ctx, name):
    ctx.step("🔍", f"Cerco {name} sul PC")
    a = find_app(name, ctx.cfg)
    if a:
        return f"{a['name']} è installato. Puoi aprirlo con open_app."
    for app_id, app_name in _flatpak_installed():
        if name.lower() in app_name.lower() or name.lower() in app_id.lower():
            return f"{app_name} è installato (Flatpak {app_id})."
    return f"{name} non è installato. Puoi installarlo con install_app."


@tool("install_app", ("Installa un programma con winget (catalogo ufficiale di Windows)." if IS_WIN else
                      "Installa un programma da Flathub (non serve la password).") + " Chiede conferma all'utente.",
      {"name": {"type": "string", "description": "nome del programma, es. Steam, OBS, VLC, Discord"}}, ["name"])
def install_app(ctx, name):
    if IS_WIN:
        return _winget_install(ctx, name)
    if not shutil.which("flatpak"):
        return "Flatpak non c'è su questo PC: installa il programma dal gestore software della tua distribuzione."
    ctx.step("🔍", f"Cerco {name} su Flathub")
    out = subprocess.run(["flatpak", "search", "--columns=application,name,description", name],
                         capture_output=True, text=True, timeout=60).stdout
    rows = [l.split("\t") for l in out.splitlines() if l.count("\t") >= 1]
    if not rows:
        return f"Non ho trovato '{name}' su Flathub."
    names = [r[1] for r in rows]
    best = difflib.get_close_matches(name, names, n=1, cutoff=0.0)
    row = rows[names.index(best[0])] if best else rows[0]
    app_id, app_name = row[0], row[1]
    for installed_id, _ in _flatpak_installed():
        if installed_id == app_id:
            return f"{app_name} è già installato."
    if not ctx.confirm(f"Installo {app_name} da Flathub?"):
        return "L'utente non ha voluto installarlo."
    ctx.step("⬇️", f"Installo {app_name} (può volerci qualche minuto)")
    r = subprocess.run(["flatpak", "install", "--user", "-y", "--noninteractive", "flathub", app_id],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        return f"Installazione non riuscita: {(r.stderr or r.stdout)[-300:]}"
    return f"Ho installato {app_name}. Puoi aprirlo con open_app."


def _steam_search(game):
    url = ("https://store.steampowered.com/api/storesearch/?l=italian&cc=IT&term="
           + urllib.parse.quote(game))
    req = urllib.request.Request(url, headers={"User-Agent": "nexus-assistant"})
    with urllib.request.urlopen(req, timeout=15) as r:
        items = json.loads(r.read()).get("items", [])
    return [(i["id"], i["name"]) for i in items]


@tool("steam_game", "Giochi Steam: installa o avvia un gioco cercandolo per nome. "
      "Apre Steam direttamente sulla pagina di installazione o fa partire il gioco.",
      {"game": {"type": "string", "description": "nome del gioco, es. Portal 2, Counter-Strike 2"},
       "action": {"type": "string", "enum": ["installa", "avvia", "pagina"]}}, ["game", "action"])
def steam_game(ctx, game, action="installa"):
    has_steam = find_app("steam", ctx.cfg) or any("steam" in i.lower() for i, _ in _flatpak_installed())
    if not has_steam:
        return "Steam non è installato. Prima installalo con install_app('Steam')."
    ctx.step("🎮", f"Cerco {game} su Steam")
    try:
        results = _steam_search(game)
    except Exception as e:
        return f"Non riesco a cercare su Steam: {e}"
    if not results:
        return f"Non trovo '{game}' su Steam."
    names = [n for _, n in results]
    best = difflib.get_close_matches(game, names, n=1, cutoff=0.0)
    appid, name = results[names.index(best[0])] if best else results[0]
    uri = {"installa": f"steam://install/{appid}", "avvia": f"steam://rungameid/{appid}",
           "pagina": f"steam://store/{appid}"}.get(action, f"steam://store/{appid}")
    ctx.step("🎮", f"{action.capitalize()}: {name}")
    open_path(uri)
    if action == "installa":
        return f"Ho aperto Steam sull'installazione di {name}: conferma nella finestra di Steam."
    if action == "avvia":
        return f"Sto avviando {name} con Steam."
    return f"Ho aperto la pagina di {name} su Steam."
