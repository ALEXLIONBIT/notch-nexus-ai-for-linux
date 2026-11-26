"""Differenze tra sistemi operativi (Linux / Windows) in un posto solo."""
import os
import subprocess
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
FROZEN = bool(getattr(sys, "frozen", False))        # app impacchettata (PyInstaller)
# su Windows i processi figli non devono aprire finestre nere della console
NO_WINDOW = 0x08000000 if IS_WIN else 0
APPIMAGE = os.environ.get("APPIMAGE", "")            # percorso del file .AppImage (app Linux impacchettata)
PACKAGED = FROZEN                                     # app impacchettata: aggiornamenti dalle release GitHub
RELEASE_PREFIX = "windows-v" if IS_WIN else "linux-v"


def run(cmd, **kw):
    """subprocess.run che su Windows non apre la console."""
    if IS_WIN:
        kw.setdefault("creationflags", NO_WINDOW)
    return subprocess.run(cmd, **kw)


def popen(cmd, **kw):
    """Avvia un programma staccato da NEXUS (non si chiude se NEXUS si chiude)."""
    kw.setdefault("stdout", subprocess.DEVNULL)
    kw.setdefault("stderr", subprocess.DEVNULL)
    if IS_WIN:
        kw.setdefault("creationflags", NO_WINDOW | 0x00000200)   # CREATE_NEW_PROCESS_GROUP
    else:
        kw.setdefault("start_new_session", True)
    return subprocess.Popen(cmd, **kw)


def open_path(target):
    """Apre file, cartelle, link e URI (steam://, ms-settings:…) con il programma predefinito."""
    target = str(target)
    if IS_WIN:
        os.startfile(target)                            # noqa: S606 (solo Windows)
    else:
        popen(["xdg-open", target])


def _win_known_folder(csidl):
    import ctypes
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:
        return Path(buf.value)
    return None


def _xdg_dir(name):
    try:
        out = subprocess.run(["xdg-user-dir", name], capture_output=True, text=True).stdout.strip()
        if out and Path(out).is_dir():
            return Path(out)
    except FileNotFoundError:
        pass
    return None


def desktop_dir():
    if IS_WIN:
        return _win_known_folder(0x0010) or Path.home() / "Desktop"     # CSIDL_DESKTOPDIRECTORY (anche OneDrive)
    return _xdg_dir("DESKTOP") or Path.home() / "Desktop"


def pictures_dir():
    if IS_WIN:
        return _win_known_folder(0x0027) or Path.home() / "Pictures"    # CSIDL_MYPICTURES
    return _xdg_dir("PICTURES") or Path.home() / "Pictures"


def os_name():
    if IS_WIN:
        import platform
        rel = platform.release()
        try:
            if int(platform.version().split(".")[2]) >= 22000:
                rel = "11"
        except (IndexError, ValueError):
            pass
        return f"Windows {rel}"
    de = os.environ.get("XDG_CURRENT_DESKTOP", "")
    return "Linux, desktop KDE Plasma" if "KDE" in de.upper() else f"Linux, desktop {de or 'grafico'}"


def fix_gui_env():
    """Un servizio partito prima della sessione grafica non ha WAYLAND_DISPLAY / DISPLAY: senza, gli screenshot
    (Spectacle) e le finestre falliscono. Li riprende da systemd (dove KDE/GNOME li pubblicano) o dai socket."""
    if IS_WIN:
        return
    keys = ("WAYLAND_DISPLAY", "DISPLAY", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "DBUS_SESSION_BUS_ADDRESS")
    if all(os.environ.get(k) for k in keys[:2]) and os.environ.get("XDG_CURRENT_DESKTOP"):
        return
    try:
        out = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True,
                             timeout=5).stdout
        for line in out.splitlines():
            k, _, v = line.partition("=")
            if k in keys and v and not os.environ.get(k):
                os.environ[k] = v
    except (OSError, subprocess.SubprocessError):
        pass
    rt = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    if not os.environ.get("WAYLAND_DISPLAY"):
        socks = sorted(p.name for p in rt.glob("wayland-*") if not p.name.endswith(".lock"))
        if socks:
            os.environ["WAYLAND_DISPLAY"] = socks[0]
    if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("XDG_SESSION_TYPE"):
        os.environ["XDG_SESSION_TYPE"] = "wayland"
    if not os.environ.get("DISPLAY"):
        xs = sorted(Path("/tmp/.X11-unix").glob("X*"), key=lambda p: p.stat().st_mtime)
        if xs:
            os.environ["DISPLAY"] = ":" + xs[-1].name[1:]
