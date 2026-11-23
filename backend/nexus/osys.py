"""Differenze tra sistemi operativi (Linux / Windows) in un posto solo."""
import os
import subprocess
import sys
from pathlib import Path

IS_WIN = sys.platform == "win32"
FROZEN = bool(getattr(sys, "frozen", False))        # app impacchettata (PyInstaller)
# su Windows i processi figli non devono aprire finestre nere della console
NO_WINDOW = 0x08000000 if IS_WIN else 0


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
