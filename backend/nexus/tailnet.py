"""Tailscale dal PC: controlla, installa e collega il client ufficiale (Windows e Linux), dalle impostazioni di NEXUS."""
import json
import os
import shutil
import time
from pathlib import Path

from .osys import IS_WIN, run, popen, open_path


def cli():
    exe = shutil.which("tailscale")
    if exe:
        return exe
    if IS_WIN:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
            p = Path(base) / "Tailscale" / "tailscale.exe"
            if base and p.exists():
                return str(p)
    return None


def status():
    exe = cli()
    if not exe:
        return {"installed": False, "state": "NonInstallato", "ip": "", "name": "", "authURL": ""}
    try:
        r = run([exe, "status", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=10)
        s = json.loads(r.stdout or "{}")
    except Exception as e:
        return {"installed": True, "state": "Spento", "ip": "", "name": "", "authURL": "", "error": str(e)[:120]}
    me = s.get("Self") or {}
    ips = s.get("TailscaleIPs") or me.get("TailscaleIPs") or []
    return {"installed": True, "state": s.get("BackendState") or "Spento", "ip": ips[0] if ips else "",
            "name": (me.get("DNSName") or "").rstrip("."), "authURL": s.get("AuthURL") or ""}


def install(step):
    if IS_WIN:
        step("Installo Tailscale con winget (Windows chiederà il permesso)…")
        run(["winget", "install", "-e", "--id", "Tailscale.Tailscale", "--silent", "--accept-package-agreements",
             "--accept-source-agreements", "--disable-interactivity"], capture_output=True, timeout=1800)
    elif shutil.which("pacman"):
        step("Installo Tailscale (ti chiederà la password)…")
        run(["pkexec", "sh", "-c", "pacman -S --needed --noconfirm tailscale && systemctl enable --now tailscaled"], timeout=1800)
    else:
        step("Installo Tailscale con lo script ufficiale (ti chiederà la password)…")
        run(["pkexec", "sh", "-c", "curl -fsSL https://tailscale.com/install.sh | sh && systemctl enable --now tailscaled"], timeout=1800)
    if not cli():
        raise RuntimeError("installazione di Tailscale non riuscita")


def connect(emit):
    """Installa se serve, avvia il login e apre il link nel browser; aspetta che sia collegato."""
    def step(t):
        emit(dict(status(), working=True, text=t))
    try:
        if not cli():
            install(step)
        st = status()
        if st["state"] == "Running":
            emit(dict(st, working=False, text="Già collegato"))
            return
        step("Avvio il login…")
        exe = cli()
        if IS_WIN:
            popen([exe, "up", "--unattended"])
        else:
            # su Linux "up" vuole i permessi: una volta sola, e da lì in poi l'utente può usare tailscale senza sudo
            popen(["pkexec", exe, "up", f"--operator={os.environ.get('USER', '')}"])
        opened = ""
        for _ in range(300):
            time.sleep(2)
            st = status()
            if st["state"] == "Running":
                emit(dict(st, working=False, text="Collegato!"))
                return
            if st["authURL"] and st["authURL"] != opened:
                opened = st["authURL"]
                open_path(opened)
                emit(dict(st, working=True, text="Accedi nel browser che si è aperto"))
        emit(dict(status(), working=False, text="Tempo scaduto: riprova"))
    except Exception as e:
        emit(dict(status(), working=False, text="", error=str(e)[:200]))
