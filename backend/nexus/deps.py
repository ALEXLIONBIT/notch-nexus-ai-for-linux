"""Aggiornamenti di quello che sta attorno a NEXUS: Ollama, i modelli scaricati e i programmi del sistema
che NEXUS usa (screenshot, OCR, Tailscale…). Personalizza → Aggiornamenti → "Controlla".

check() ritorna una lista di voci {id, name, current, latest, state, note, action}:
  state  "ok" | "update" | "info" | "error"
  action cosa fa il tasto "Aggiorna" (apply): None se da qui non si può aggiornare.
"""
import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .osys import IS_WIN, run, popen

OLLAMA_RELEASE = "https://api.github.com/repos/ollama/ollama/releases/latest"
REGISTRY = "https://registry.ollama.ai/v2"
UA = {"User-Agent": "nexus-assistant"}

# pacchetti di sistema che NEXUS usa (nomi di Arch, Debian/Ubuntu, Fedora): gli altri si contano soltanto
SYS_PKGS = re.compile(r"^(ollama(-cuda|-rocm|-vulkan)?|tesseract(-ocr)?(-data|-langpack)?(-ita|-eng)?|"
                      r"spectacle|grim|gnome-screenshot|tailscale|wmctrl|xdotool|x11-utils|xorg-xprop|xclip|xsel|"
                      r"wl-clipboard|playerctl|brightnessctl|portaudio|libportaudio2|pipewire|"
                      r"qt6-tools|qdbus-qt6|qt6-qttools|pyside6|python-pyside6|kwin|kwin-wayland)$")

# programmi aggiornabili con winget su Windows
WINGET_IDS = {"Ollama.Ollama": "Ollama", "tailscale.tailscale": "Tailscale", "UB-Mannheim.TesseractOCR": "Tesseract OCR"}


def _get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ver(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4])


def _local(p):
    url = (p or {}).get("base_url", "")
    return any(h in url for h in ("127.0.0.1", "localhost", "[::1]"))


# ---------------------------------------------------------------- Ollama
def ollama_latest():
    return json.loads(_get(OLLAMA_RELEASE))["tag_name"].lstrip("v")


def ollama_version(p):
    from .models import _req
    with _req(p, "/api/version", timeout=6) as r:
        return json.loads(r.read()).get("version", "")


def _owner(path):
    """Chi ha installato questo file: ('pacman'|'apt'|'dnf', pacchetto) oppure (None, '') se nessun gestore."""
    real = os.path.realpath(path)
    for tool, cmd in (("pacman", ["pacman", "-Qqo", real]), ("apt", ["dpkg", "-S", real]),
                      ("dnf", ["rpm", "-qf", "--qf", "%{NAME}\n", real])):
        if not shutil.which(cmd[0]):
            continue
        try:
            r = run(cmd, capture_output=True, text=True, timeout=10)
        except Exception:
            continue
        if r.returncode == 0 and r.stdout.strip():
            out = r.stdout.strip().splitlines()[0]
            return tool, (out.split(":")[0] if tool == "apt" else out).strip()
    return None, ""


def _ollama_item(p, sys_updates):
    item = {"id": "ollama", "name": "Ollama (motore dei modelli)", "current": "", "latest": "", "state": "ok",
            "note": "", "action": None}
    try:
        item["current"] = ollama_version(p)
    except Exception:
        item.update(state="error", note="Ollama non risponde: è acceso?")
        return item
    try:
        item["latest"] = ollama_latest()
    except Exception as e:
        item.update(state="error", note="non riesco a sapere l'ultima versione: " + str(e)[:80])
        return item
    if _ver(item["latest"]) <= _ver(item["current"]):
        return item
    if not _local(p):
        item.update(state="info", note=f"è sull'altro PC ({p.get('name', '')}): aggiornalo da lì")
        return item
    item["state"] = "update"
    if IS_WIN:
        item.update(action="ollama_win", note="lo scarico e lo installo io")
        return item
    from .winsetup import find_ollama
    exe = find_ollama()
    tool, pkg = _owner(exe) if exe else (None, "")
    if tool:
        offered = next((u for u in sys_updates if u["name"] == pkg), None)
        if offered:
            got = re.sub(r"-[\d.]+$", "", offered["new"].split(":")[-1])
            item.update(action="system", latest=got, note="arriva coi pacchetti del sistema" +
                        (f" (su ollama.com c'è già la {item['latest']})" if _ver(item["latest"]) > _ver(got) else ""))
        else:
            item.update(state="info", note=f"installato coi pacchetti del sistema ({pkg}): la versione nuova "
                                           "non è ancora arrivata lì, riprova tra qualche giorno")
    else:
        item.update(action="ollama_script", note="lo aggiorno con lo script ufficiale (ti chiedo la password)")
    return item


# ---------------------------------------------------------------- modelli di Ollama
def _registry_digest(name):
    """Digest del manifest su registry.ollama.ai; None se il modello non viene da lì (creato in locale, hf.co…)."""
    base, _, tag = name.partition(":")
    if base.startswith(("hf.co/", "huggingface.co/")) or base.count("/") > 1:
        return None
    ns, _, model = base.rpartition("/")
    try:
        body = _get(f"{REGISTRY}/{ns or 'library'}/{model}/manifests/{tag or 'latest'}",
                    {"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return hashlib.sha256(body).hexdigest()


def outdated_models(p):
    """Modelli installati che su ollama.com hanno una versione nuova (stesso nome, contenuto aggiornato)."""
    from .models import _req
    with _req(p, "/api/tags") as r:
        models = json.loads(r.read()).get("models", [])

    def one(m):
        try:
            d = _registry_digest(m["name"])
        except Exception:
            return None
        return m["name"].removesuffix(":latest") if d and d != m.get("digest") else None
    with ThreadPoolExecutor(8) as ex:
        return [n for n in ex.map(one, models) if n], len(models)


def _models_item(p):
    item = {"id": "models", "name": "Modelli di Ollama", "current": "", "latest": "", "state": "ok",
            "note": "", "action": None, "models": []}
    try:
        old, total = outdated_models(p)
    except Exception as e:
        item.update(state="error", note="non riesco a controllarli: " + str(e)[:80])
        return item
    item["current"] = f"{total} installati"
    if old:
        item.update(state="update", models=old, action="models",
                    latest=f"{len(old)} da aggiornare", note=", ".join(old[:8]) + ("…" if len(old) > 8 else ""))
    return item


# ---------------------------------------------------------------- pacchetti del sistema
def distro_tool():
    if IS_WIN:
        return "winget" if shutil.which("winget") else None
    for t in ("pacman", "apt-get", "dnf"):
        if shutil.which(t):
            return t
    return None


def system_updates():
    """Aggiornamenti in attesa nel sistema: [{name, old, new}]. Senza password: non cambia niente."""
    tool = distro_tool()
    out = []
    try:
        if tool == "pacman":
            cmd = ["checkupdates"] if shutil.which("checkupdates") else ["pacman", "-Qu"]
            txt = run(cmd, capture_output=True, text=True, timeout=180).stdout
            for l in txt.splitlines():
                m = re.match(r"(\S+) (\S+) -> (\S+)", l)
                if m:
                    out.append({"name": m[1], "old": m[2], "new": m[3]})
        elif tool == "apt-get":
            txt = run(["apt", "list", "--upgradable"], capture_output=True, text=True, timeout=60).stdout
            for l in txt.splitlines():
                m = re.match(r"([^/\s]+)/\S+ (\S+) \S+ \[\S+: (\S+)\]", l)
                if m:
                    out.append({"name": m[1], "old": m[3], "new": m[2]})
        elif tool == "dnf":
            txt = run(["dnf", "-q", "check-update"], capture_output=True, text=True, timeout=180).stdout
            for l in txt.splitlines():
                m = re.match(r"(\S+)\.\w+\s+(\S+)\s+\S+$", l)
                if m:
                    out.append({"name": m[1], "old": "", "new": m[2]})
        elif tool == "winget":
            for wid in WINGET_IDS:
                txt = run(["winget", "list", "--id", wid, "-e", "--accept-source-agreements",
                           "--disable-interactivity"], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60).stdout
                line = next((l for l in txt.splitlines() if wid.lower() in l.lower()), "")
                vers = re.findall(r"\d+(?:\.\d+)+", line[line.lower().find(wid.lower()) + len(wid):] if line else "")
                if len(vers) >= 2 and _ver(vers[1]) > _ver(vers[0]):
                    out.append({"name": wid, "old": vers[0], "new": vers[1]})
    except Exception as e:
        print("controllo pacchetti di sistema:", e)
    return out


def _system_item(updates):
    tool = distro_tool()
    item = {"id": "system", "name": "Programmi del sistema usati da NEXUS", "current": "", "latest": "",
            "state": "ok", "note": "", "action": None}
    if not tool:
        item.update(state="info", note="non riconosco il gestore dei pacchetti di questo sistema")
        return item
    if tool == "winget":
        mine = [u for u in updates if u["name"] in WINGET_IDS and u["name"] != "Ollama.Ollama"]
        names = [f"{WINGET_IDS[u['name']]} {u['old']} → {u['new']}" for u in mine]
        others = 0
    else:
        mine = [u for u in updates if SYS_PKGS.match(u["name"])]
        names = [f"{u['name']} {u['old']} → {u['new']}".replace("  ", " ") for u in mine]
        others = len(updates) - len(mine)
    if mine:
        item.update(state="update", action="system", latest=f"{len(mine)} da aggiornare", note=", ".join(names))
    if others:
        item["note"] = (item["note"] + "\n" if item["note"] else "") + \
            f"Nel sistema ci sono altri {others} aggiornamenti" + ("" if mine else " (non servono a NEXUS)")
        if not mine:
            item.update(state="info", action="system")
    return item


def upgrade_command():
    """Il comando che aggiorna il sistema (lo lancio in un terminale: la password la scrivi tu)."""
    tool = distro_tool()
    if tool == "pacman":                         # Arch: gli aggiornamenti parziali non sono supportati
        return "sudo pacman -Syu"
    if tool == "apt-get":
        return "sudo apt update && sudo apt upgrade"
    if tool == "dnf":
        return "sudo dnf upgrade --refresh"
    return ""


def open_terminal(command):
    """Apre un terminale che esegue command e aspetta Invio prima di chiudersi."""
    from .osys import fix_gui_env
    fix_gui_env()
    script = f'{command}; echo; echo "Fatto. Torna su NEXUS e premi Controlla."; read -r _'
    for term, pre in (("konsole", ["-e"]), ("gnome-terminal", ["--"]), ("kgx", ["--"]), ("xfce4-terminal", ["-x"]),
                      ("mate-terminal", ["-x"]), ("tilix", ["-e"]), ("kitty", []), ("alacritty", ["-e"]),
                      ("foot", []), ("x-terminal-emulator", ["-e"]), ("xterm", ["-e"])):
        if shutil.which(term):
            popen([term, *pre, "sh", "-c", script])
            return term
    raise RuntimeError("non trovo un terminale: lancia tu « " + command + " »")


# ---------------------------------------------------------------- controllo e aggiornamento
def check(cfg):
    from .models import target
    p = target(cfg)
    with ThreadPoolExecutor(2) as ex:
        sys_f = ex.submit(system_updates)
        models_f = ex.submit(_models_item, p) if p else None
        updates = sys_f.result()
        if p:
            items = [_ollama_item(p, updates), models_f.result()]
        else:
            items = [{"id": "ollama", "name": "Ollama (motore dei modelli)", "current": "", "latest": "",
                      "state": "info", "note": "non usi Ollama: nessun motore locale da controllare", "action": None}]
    items.append(_system_item(updates))
    return items


def apply(cfg, action, status, item=None):
    """Esegue l'aggiornamento di una voce. status(testo, pct) durante il lavoro. Ritorna il messaggio finale."""
    if action == "models":
        from .models import target, pull
        p = target(cfg)
        names = (item or {}).get("models") or outdated_models(p)[0]
        for i, n in enumerate(names, 1):
            pull(p, n, lambda t, pct=-1, i=i: status(f"[{i}/{len(names)}] {t}", pct))
        return f"{len(names)} modelli aggiornati"
    if action == "ollama_script":
        if not shutil.which("pkexec"):
            open_terminal("curl -fsSL https://ollama.com/install.sh | sh")
            return "Ho aperto un terminale con l'aggiornamento di Ollama"
        status("Aggiorno Ollama (ti chiedo la password)…", -1)
        r = run(["pkexec", "sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError("aggiornamento non riuscito: " + (r.stderr or r.stdout or "annullato")[-160:])
        return "Ollama aggiornato"
    if action == "ollama_win":
        if shutil.which("winget"):
            status("Aggiorno Ollama con winget…", -1)
            r = run(["winget", "upgrade", "-e", "--id", "Ollama.Ollama", "--silent", "--accept-package-agreements",
                     "--accept-source-agreements", "--disable-interactivity"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=1800)
            if r.returncode == 0:
                return "Ollama aggiornato"
        from .config import CACHE
        status("Scarico Ollama…", -1)
        dest = CACHE / "OllamaSetup.exe"
        with urllib.request.urlopen(urllib.request.Request("https://ollama.com/download/OllamaSetup.exe",
                                                           headers=UA), timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        status("Installo Ollama…", -1)
        run([str(dest), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=1800)
        return "Ollama aggiornato"
    if action == "system":
        if IS_WIN:
            for u in system_updates():
                if u["name"] in WINGET_IDS:
                    status(f"Aggiorno {WINGET_IDS[u['name']]}…", -1)
                    run(["winget", "upgrade", "-e", "--id", u["name"], "--silent", "--accept-package-agreements",
                         "--accept-source-agreements", "--disable-interactivity"], capture_output=True, timeout=1800)
            return "Programmi aggiornati"
        cmd = upgrade_command()
        if not cmd:
            raise RuntimeError("non so aggiornare questo sistema")
        term = open_terminal(cmd)
        return f"Ho aperto {term} con « {cmd} »: scrivi lì la password"
    raise RuntimeError("aggiornamento sconosciuto: " + str(action))
