"""Permessi su Linux (primo avvio dell'AppImage): mouse e tastiera virtuali, microfono, lettura dello schermo."""
import os
import shutil
import subprocess

# regola udev per /dev/uinput + gruppo input (resta per i prossimi avvii); setfacl dà l'accesso SUBITO,
# senza dover uscire e rientrare dalla sessione
UDEV = ('echo \'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"\' '
        '> /etc/udev/rules.d/60-nexus-uinput.rules; echo uinput > /etc/modules-load.d/nexus-uinput.conf; '
        'modprobe uinput; udevadm control --reload-rules; udevadm trigger /dev/uinput; usermod -aG input "$1"; '
        'command -v setfacl >/dev/null && setfacl -m u:"$1":rw /dev/uinput; true')


def uinput_ok():
    return os.access("/dev/uinput", os.W_OK)


def status(ears=None):
    return {
        "uinput": uinput_ok(),
        "mic": bool(ears is not None and getattr(ears, "stream", None) is not None),
        "ocr": shutil.which("tesseract") is not None,
        "pkexec": shutil.which("pkexec") is not None,
    }


def grant_uinput():
    """Chiede la password (finestra di sistema) e dà a NEXUS mouse e tastiera virtuali. (ok, messaggio)"""
    if uinput_ok():
        return True, "Mouse e tastiera: già a posto."
    if not shutil.which("pkexec"):
        return False, "Manca pkexec: da terminale esegui NEXUS con --permessi."
    user = os.environ.get("USER") or os.getlogin()
    r = subprocess.run(["pkexec", "sh", "-c", UDEV, "sh", user], capture_output=True, text=True)
    if r.returncode in (126, 127):
        return False, "Password annullata."
    if uinput_ok():
        return True, "Fatto: ora posso usare mouse e tastiera."
    if r.returncode == 0:
        return True, "Fatto: vale dal prossimo accesso (esci e rientra)."
    return False, (r.stderr or r.stdout or "non riuscito").strip()[-160:]
