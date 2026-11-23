"""Trovare e installare programmi (Flatpak, senza password) e giochi Steam."""
import difflib
import json
import shutil
import subprocess
import urllib.parse
import urllib.request

from . import tool
from .apps import find_app


def _flatpak_installed():
    if not shutil.which("flatpak"):
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


@tool("install_app", "Installa un programma da Flathub (non serve la password). Chiede conferma all'utente.",
      {"name": {"type": "string", "description": "nome del programma, es. Steam, OBS, VLC, Discord"}}, ["name"])
def install_app(ctx, name):
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
    subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    if action == "installa":
        return f"Ho aperto Steam sull'installazione di {name}: conferma nella finestra di Steam."
    if action == "avvia":
        return f"Sto avviando {name} con Steam."
    return f"Ho aperto la pagina di {name} su Steam."
