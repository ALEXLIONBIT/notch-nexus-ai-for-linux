"""Tool diretti (più veloci che usare lo schermo): file, appunti, musica, luminosità, promemoria,
pagine web, Wi-Fi/Bluetooth, processi, blocco e spegnimento."""
import html
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import psutil

from . import tool
from ..osys import IS_WIN, run, popen, open_path


def _run(*cmd, timeout=15):
    return run(list(cmd), capture_output=True, text=True, timeout=timeout)


def _ps(script, timeout=20):
    """Esegue uno script PowerShell (Windows) senza finestra."""
    return run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _winrt_run(coro):
    import asyncio
    return asyncio.run(coro)


# ---------------------------------------------------------------- file
@tool("write_file", "Crea o sovrascrive un file di testo (es. appunti, script, liste).",
      {"path": {"type": "string"}, "content": {"type": "string"},
       "append": {"type": "boolean", "description": "aggiungi in fondo invece di sovrascrivere"}}, ["path", "content"])
def write_file(ctx, path, content, append=False):
    p = Path(path).expanduser()
    if p.exists() and not append and not ctx.confirm(f"Sovrascrivo il file {p.name}?"):
        return "L'utente non vuole sovrascriverlo."
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a" if append else "w", encoding="utf-8") as f:
        f.write(content)
    ctx.step("📝", f"Scritto {p.name}")
    return f"File salvato: {p}"


@tool("find_files", "Cerca file per nome nella home (es. 'tesina', '*.pdf').",
      {"pattern": {"type": "string"}, "folder": {"type": "string", "description": "cartella, default la home"}}, ["pattern"])
def find_files(ctx, pattern, folder="~"):
    base = Path(folder).expanduser()
    ctx.step("🔍", f"Cerco “{pattern}”")
    pat = pattern if any(c in pattern for c in "*?[") else f"*{pattern}*"
    found = []
    for p in base.rglob(pat):
        if any(part.startswith(".") for part in p.relative_to(base).parts):
            continue
        found.append(str(p))
        if len(found) >= 40:
            break
    return "\n".join(found) or "Nessun file trovato."


@tool("move_to_trash", "Sposta file o cartelle nel cestino (si possono recuperare).",
      {"path": {"type": "string"}}, ["path"])
def move_to_trash(ctx, path):
    p = Path(path).expanduser()
    if not p.exists():
        return f"{p} non esiste."
    if not ctx.confirm(f"Sposto nel cestino {p.name}?"):
        return "Annullato."
    if IS_WIN:
        from send2trash import send2trash
        send2trash(str(p))
    else:
        _run("gio", "trash", str(p))
    ctx.step("🗑️", f"Nel cestino: {p.name}")
    return f"{p.name} è nel cestino."


@tool("copy_move", "Copia o sposta un file/cartella.",
      {"src": {"type": "string"}, "dst": {"type": "string"}, "move": {"type": "boolean"}}, ["src", "dst"])
def copy_move(ctx, src, dst, move=False):
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    ctx.step("📁", f"{'Sposto' if move else 'Copio'} {s.name}")
    if move:
        shutil.move(str(s), str(d))
    elif s.is_dir():
        shutil.copytree(s, d / s.name if d.is_dir() else d)
    else:
        shutil.copy2(s, d)
    return "Fatto."


@tool("open_file", "Apre un file con il programma predefinito (PDF, foto, documenti…).",
      {"path": {"type": "string"}}, ["path"])
def open_file(ctx, path):
    p = Path(path).expanduser()
    if not p.exists():
        return f"{p} non esiste."
    ctx.step("📂", f"Apro {p.name}")
    open_path(p)
    return f"Ho aperto {p.name}."


# ---------------------------------------------------------------- appunti
@tool("clipboard", "Legge o scrive gli appunti (copia/incolla).",
      {"action": {"type": "string", "enum": ["leggi", "scrivi"]}, "text": {"type": "string"}}, ["action"])
def clipboard(ctx, action, text=""):
    if action == "scrivi":
        from .inputs import copy_to_clipboard
        copy_to_clipboard(text)
        ctx.step("📋", "Copiato negli appunti")
        return "Copiato negli appunti."
    if IS_WIN:
        from ._win_input import read_clipboard
        return read_clipboard()[:3000] or "(appunti vuoti)"
    for cmd in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"]):
        if shutil.which(cmd[0]):
            return _run(*cmd).stdout[:3000] or "(appunti vuoti)"
    return "Non riesco a leggere gli appunti."


# ---------------------------------------------------------------- musica e luminosità
@tool("media_control", "Controlla la musica/video in riproduzione (Spotify, YouTube nel browser, VLC…).",
      {"action": {"type": "string", "enum": ["play", "pausa", "play-pausa", "avanti", "indietro", "info"]}}, ["action"])
def media_control(ctx, action):
    if IS_WIN:
        if action == "info":
            return _win_media_info()
        from .inputs import press
        press({"avanti": "nextsong", "indietro": "previoussong"}.get(action, "playpause"))
        ctx.step("🎵", action)
        return "Fatto."
    if not shutil.which("playerctl"):
        from .inputs import press
        press({"avanti": "nextsong", "indietro": "previoussong"}.get(action, "playpause"))
        return "Fatto."
    if action == "info":
        return _run("playerctl", "metadata", "--format", "{{artist}} - {{title}} ({{status}})").stdout.strip() or "Niente in riproduzione."
    _run("playerctl", {"play": "play", "pausa": "pause", "play-pausa": "play-pause", "avanti": "next", "indietro": "previous"}[action])
    ctx.step("🎵", action)
    return "Fatto."


def _win_media_info():
    """Cosa sta suonando (Spotify, browser, Lettore multimediale…) dai controlli multimediali di Windows."""
    try:
        from winrt.windows.media.control import \
            GlobalSystemMediaTransportControlsSessionManager as Manager

        async def go():
            ses = (await Manager.request_async()).get_current_session()
            if ses is None:
                return "Niente in riproduzione."
            props = await ses.try_get_media_properties_async()
            playing = ses.get_playback_info().playback_status == 4
            return f"{props.artist} - {props.title} ({'in riproduzione' if playing else 'in pausa'})"
        return _winrt_run(go())
    except Exception as e:
        return f"Non riesco a sapere cosa suona: {e}"


@tool("set_brightness", "Imposta la luminosità dello schermo in percentuale.",
      {"percent": {"type": "integer"}}, ["percent"])
def set_brightness(ctx, percent):
    p = max(1, min(100, int(percent)))
    ctx.step("🔆", f"Luminosità {p}%")
    if IS_WIN:
        r = _ps(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop)"
                f" | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={p}}}")
        if r.returncode == 0:
            return f"Luminosità al {p}%."
        return "Su questo PC Windows non si può cambiare la luminosità da programma (succede con i monitor esterni)."
    if shutil.which("brightnessctl"):
        _run("brightnessctl", "set", f"{p}%")
        return f"Luminosità al {p}%."
    q = "qdbus6"
    mx = _run(q, "org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement/Actions/BrightnessControl",
              "brightnessMax").stdout.strip()
    if mx.isdigit():
        _run(q, "org.kde.Solid.PowerManagement", "/org/kde/Solid/PowerManagement/Actions/BrightnessControl",
             "setBrightness", str(int(mx) * p // 100))
        return f"Luminosità al {p}%."
    return "Non riesco a cambiare la luminosità su questo PC."


# ---------------------------------------------------------------- promemoria
def notify(title, text):
    """Notifica di sistema (notify-send su Linux, notifica 'toast' su Windows)."""
    try:
        if IS_WIN:
            import html as h
            xml = (f"<toast><visual><binding template='ToastGeneric'><text>{h.escape(title)}</text>"
                   f"<text>{h.escape(text)}</text></binding></visual></toast>").replace("'", "''")
            _ps("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null;"
                f"$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml('{xml}');"
                "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show("
                "[Windows.UI.Notifications.ToastNotification]::new($x))")
        else:
            _run("notify-send", "-a", "NEXUS", title, text)
    except Exception as e:
        print("notifica non riuscita:", e)


@tool("reminder", "Imposta un promemoria: tra N minuti mostra una notifica (e NEXUS lo dice a voce).",
      {"minutes": {"type": "number"}, "text": {"type": "string"}}, ["minutes", "text"])
def reminder(ctx, minutes, text):
    secs = max(5, int(float(minutes) * 60))

    def fire():
        time.sleep(secs)
        notify("Promemoria", text)
        try:
            ctx.n.voice.speak(f"Promemoria: {text}")
        except Exception:
            pass
    threading.Thread(target=fire, daemon=True).start()
    ctx.step("⏰", f"Promemoria tra {minutes} min")
    return f"Ok, tra {minutes} minuti ti ricordo: {text}."


# ---------------------------------------------------------------- web
@tool("read_webpage", "Legge il testo di una pagina web (per rispondere senza aprire il browser).",
      {"url": {"type": "string"}}, ["url"])
def read_webpage(ctx, url):
    if "://" not in url:
        url = "https://" + url
    ctx.step("🌐", f"Leggo {url[:60]}")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NEXUS" if IS_WIN else "Mozilla/5.0 (X11; Linux x86_64) NEXUS"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", raw)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", text).strip()[:4000] or "(pagina vuota)"


# ---------------------------------------------------------------- rete
@tool("toggle_radio", "Accende o spegne Wi-Fi o Bluetooth.",
      {"device": {"type": "string", "enum": ["wifi", "bluetooth"]}, "on": {"type": "boolean"}}, ["device", "on"])
def toggle_radio(ctx, device, on):
    if IS_WIN:
        msg = _win_radio(device, on)
        ctx.step("📶", f"{device} {'acceso' if on else 'spento'}")
        return msg
    if device == "wifi":
        _run("nmcli", "radio", "wifi", "on" if on else "off")
    else:
        _run("bluetoothctl", "power", "on" if on else "off")
    ctx.step("📶", f"{device} {'acceso' if on else 'spento'}")
    return f"{device} {'acceso' if on else 'spento'}."


def _win_radio(device, on):
    """Wi-Fi e Bluetooth su Windows con Windows.Devices.Radios (non servono permessi da amministratore)."""
    from winrt.windows.devices.radios import Radio, RadioKind, RadioState

    async def go():
        await Radio.request_access_async()
        kind = RadioKind.WI_FI if device == "wifi" else RadioKind.BLUETOOTH
        radios = [r for r in await Radio.get_radios_async() if r.kind == kind]
        if not radios:
            return f"Questo PC non ha {device}."
        for r in radios:
            await r.set_state_async(RadioState.ON if on else RadioState.OFF)
        return f"{device} {'acceso' if on else 'spento'}."
    try:
        return _winrt_run(go())
    except Exception as e:
        return f"Non riesco a cambiare {device}: {e}"


# ---------------------------------------------------------------- processi e sistema
@tool("processes", "Elenca i programmi che usano più CPU/RAM.")
def processes(ctx):
    ctx.step("📊", "Guardo i processi")
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            procs.append((p.info["memory_info"].rss / 1e6, p.info["name"], p.info["pid"]))
        except Exception:
            pass
    procs.sort(reverse=True)
    return "\n".join(f"{n} (pid {pid}): {mb:.0f} MB" for mb, n, pid in procs[:12])


@tool("close_program", "Chiude un programma per nome (es. 'firefox').", {"name": {"type": "string"}}, ["name"])
def close_program(ctx, name):
    if not ctx.confirm(f"Chiudo {name}? Il lavoro non salvato potrebbe andare perso."):
        return "Annullato."
    ctx.step("✖️", f"Chiudo {name}")
    if IS_WIN:
        q = name.lower().removesuffix(".exe")
        found = []
        for p in psutil.process_iter(["name"]):
            n = (p.info["name"] or "").lower()
            if q in n and n not in ("nexus.exe", "explorer.exe", "csrss.exe", "winlogon.exe"):
                found.append(p)
        for p in found:
            try:
                p.terminate()
            except Exception:
                pass
        return "Chiuso." if found else f"Non ho trovato {name} in esecuzione."
    r = _run("pkill", "-f", "-i", name)
    return "Chiuso." if r.returncode == 0 else f"Non ho trovato {name} in esecuzione."


@tool("power", "Blocca lo schermo, sospende, riavvia o spegne il PC.",
      {"action": {"type": "string", "enum": ["blocca", "sospendi", "riavvia", "spegni"]}}, ["action"])
def power(ctx, action):
    if action != "blocca" and not ctx.confirm(f"Vuoi davvero {action} il PC?"):
        return "Annullato."
    ctx.step("⏻", action.capitalize())
    if IS_WIN:
        cmd = {"blocca": ["rundll32.exe", "user32.dll,LockWorkStation"],
               "sospendi": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
               "riavvia": ["shutdown", "/r", "/t", "0"], "spegni": ["shutdown", "/s", "/t", "0"]}[action]
    else:
        cmd = {"blocca": ["loginctl", "lock-session"], "sospendi": ["systemctl", "suspend"],
               "riavvia": ["systemctl", "reboot"], "spegni": ["systemctl", "poweroff"]}[action]
    popen(cmd)
    return "Fatto."
