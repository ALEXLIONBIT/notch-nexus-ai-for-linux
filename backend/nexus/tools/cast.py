"""Condividere lo schermo con una TV (Miracast / Chromecast) tramite GNOME Network Displays.

La TV si sceglie per nome: NEXUS apre Network Displays, aspetta che la TV compaia, la clicca
e conferma la finestra di condivisione schermo di KDE.
"""
import difflib
import re
import subprocess
import time

from . import tool
from .screen import screenshot, ocr, find_text

APP_ID = "org.gnome.NetworkDisplays"
SERVICES = {"_display._tcp": "Miracast", "_googlecast._tcp": "Chromecast", "_airplay._tcp": "AirPlay"}


def _unescape(s):
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), s)


def discover(timeout=6):
    """[{name, kind, ip}] dei dispositivi sulla rete locale."""
    try:
        out = subprocess.run(["avahi-browse", "-arkt", "-p"], capture_output=True, text=True, timeout=timeout + 2).stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    found = {}
    for line in out.splitlines():
        p = line.split(";")
        if len(p) < 8 or p[0] != "=" or p[4] not in SERVICES or ":" in p[7]:
            continue
        name = _unescape(p[3])
        if p[4] == "_googlecast._tcp" and ("Nest-Mini" in name or "Cast-Group" in name or "Nest-Hub" in name):
            continue   # altoparlanti: non mostrano lo schermo
        key = (name, SERVICES[p[4]])
        found[key] = {"name": name, "kind": SERVICES[p[4]], "ip": p[7]}
    return sorted(found.values(), key=lambda d: d["name"].lower())


@tool("list_tvs", "Cerca le TV e i dispositivi a cui si può trasmettere lo schermo (Miracast, Chromecast, AirPlay).")
def list_tvs(ctx):
    ctx.step("📡", "Cerco le TV sulla rete")
    devs = discover()
    if not devs:
        return "Non ho trovato TV sulla rete."
    return "; ".join(f"{d['name']} ({d['kind']})" for d in devs) + \
        ". Per lo schermo funzionano i dispositivi Miracast e Chromecast."


@tool("cast_screen", "Condivide (trasmette) lo schermo del PC su una TV, scelta per nome, es. 'TV Cucina'.",
      {"tv": {"type": "string", "description": "nome (anche parziale) della TV"}}, ["tv"])
def cast_screen(ctx, tv):
    devs = [d for d in discover() if d["kind"] in ("Miracast", "Chromecast")]
    names = [d["name"] for d in devs]
    match = difflib.get_close_matches(tv, names, n=1, cutoff=0.3) or [n for n in names if tv.lower() in n.lower()]
    target = match[0] if match else tv
    ctx.step("📺", f"Preparo lo streaming verso {target}")
    subprocess.Popen(["flatpak", "run", APP_ID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    from . import inputs
    from PIL import Image
    # aspetta che la TV compaia nella lista di Network Displays
    words = re.sub(r"[\[\]]", " ", target).split()
    probe = " ".join(w for w in words if len(w) > 1) or target
    pos = None
    for _ in range(12):
        time.sleep(2)
        shot = screenshot()
        inputs._size = Image.open(shot).size
        pos, _ = find_text(ocr(shot), probe)
        if pos:
            break
    if not pos:
        return (f"Ho aperto Network Displays ma non vedo '{target}' nella lista. "
                "Controlla che la TV sia accesa e sulla stessa rete Wi-Fi.")
    ctx.step("🖱️", f"Seleziono {target}")
    x, y = inputs.to_norm(pos[0], pos[1])
    inputs.move(x, y)
    inputs.click_btn("left", 1)
    # finestra di KDE "Condividi schermo": conferma
    for _ in range(8):
        time.sleep(1.5)
        shot = screenshot()
        lines = ocr(shot)
        for label in ("Condividi", "Share", "OK"):
            p, score = find_text(lines, label)
            if p and score > 0.8:
                ctx.step("🖱️", f"Confermo ({label})")
                x, y = inputs.to_norm(p[0], p[1])
                inputs.move(x, y)
                inputs.click_btn("left", 1)
                return f"Sto trasmettendo lo schermo su {target}. Sulla TV potrebbe servire accettare la connessione."
    return (f"Ho selezionato {target}: se la TV chiede di accettare la connessione, conferma col telecomando. "
            "Se compare una finestra di condivisione schermo, sceglila tu.")


@tool("stop_cast", "Ferma la trasmissione dello schermo sulla TV.")
def stop_cast(ctx):
    ctx.step("📺", "Fermo lo streaming")
    subprocess.run(["flatpak", "kill", APP_ID], capture_output=True, timeout=10)
    return "Ho fermato la trasmissione."
