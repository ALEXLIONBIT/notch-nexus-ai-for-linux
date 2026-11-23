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
from ..osys import IS_WIN

APP_ID = "org.gnome.NetworkDisplays"
SERVICES = {"_display._tcp": "Miracast", "_googlecast._tcp": "Chromecast", "_airplay._tcp": "AirPlay"}


def _unescape(s):
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), s)


def _discover_zeroconf(timeout=6):
    """Windows (niente avahi): mDNS con la libreria zeroconf."""
    from zeroconf import ServiceBrowser, Zeroconf
    found = {}

    class L:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, 2000)
            kind = SERVICES.get(type_.replace(".local.", ""))
            if not info or not kind:
                return
            label = name.replace("." + type_, "")
            if info.properties:                          # i Chromecast hanno il nome vero nel campo "fn"
                fn = info.properties.get(b"fn")
                label = fn.decode("utf-8", "replace") if fn else label
            if kind == "Chromecast" and any(x in label for x in ("Nest Mini", "Nest-Mini", "Cast-Group", "Nest Hub")):
                return
            ips = info.parsed_addresses()
            found[(label, kind)] = {"name": label, "kind": kind, "ip": ips[0] if ips else ""}

        def update_service(self, *a):
            pass

        def remove_service(self, *a):
            pass
    zc = Zeroconf()
    try:
        ServiceBrowser(zc, [t + ".local." for t in SERVICES], L())
        time.sleep(timeout)
    finally:
        zc.close()
    return sorted(found.values(), key=lambda d: d["name"].lower())


def discover(timeout=6):
    """[{name, kind, ip}] dei dispositivi sulla rete locale."""
    if IS_WIN:
        return _discover_zeroconf(timeout)
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


def _cast_windows(ctx, target):
    """Windows ha Miracast integrato: Win+K apre 'Trasmetti', poi si clicca la TV per nome."""
    from . import inputs
    from PIL import Image
    inputs.press("win+k")
    t0 = time.time()
    while time.time() - t0 < 25:
        time.sleep(1.5)
        shot = screenshot()
        inputs._size = Image.open(shot).size
        pos, _ = find_text(ocr(shot), target)
        if pos:
            x, y = inputs.to_norm(pos[0], pos[1])
            inputs.move(x, y)
            inputs.click_btn("left")
            ctx.step("📺", f"Mi collego a {pos[2]}")
            return f"Ho avviato la trasmissione dello schermo su {pos[2]} (Miracast di Windows)."
    inputs.press("esc")
    return (f"Non vedo '{target}' nel pannello Trasmetti di Windows. Su Windows lo schermo si trasmette solo "
            "alle TV Miracast (le Chromecast funzionano solo da Chrome: menu ⋮ → Trasmetti).")


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
    if IS_WIN:
        return _cast_windows(ctx, target)
    import shutil
    has_flatpak = shutil.which("flatpak") and subprocess.run(["flatpak", "info", APP_ID], capture_output=True).returncode == 0
    if has_flatpak:
        cmd = ["flatpak", "run", APP_ID]
    elif shutil.which("gnome-network-displays"):
        cmd = ["gnome-network-displays"]
    else:
        return ("Per trasmettere lo schermo serve GNOME Network Displays: "
                "flatpak install --user flathub org.gnome.NetworkDisplays (oppure sudo apt install gnome-network-displays).")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
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
    if IS_WIN:
        from . import inputs
        from PIL import Image
        inputs.press("win+k")
        time.sleep(2)
        shot = screenshot()
        inputs._size = Image.open(shot).size
        pos, _ = find_text(ocr(shot), "Disconnetti")
        if not pos:
            pos, _ = find_text(ocr(shot), "Disconnect")
        if pos:
            inputs.move(*inputs.to_norm(pos[0], pos[1]))
            inputs.click_btn("left")
            return "Ho fermato la trasmissione."
        inputs.press("esc")
        return "Non vedo nessuna trasmissione attiva."
    subprocess.run(["flatpak", "kill", APP_ID], capture_output=True, timeout=10)
    subprocess.run(["pkill", "-f", "gnome-network-displays"], capture_output=True, timeout=10)
    return "Ho fermato la trasmissione."
