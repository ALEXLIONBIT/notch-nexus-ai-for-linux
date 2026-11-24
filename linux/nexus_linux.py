"""NEXUS per Linux (AppImage): backend e interfaccia nello stesso programma.

  NEXUS.AppImage              avvia l'assistente (una sola copia alla volta)
  NEXUS.AppImage --permessi   una volta sola: permesso per mouse e tastiera virtuali (/dev/uinput)
  NEXUS.AppImage --selftest   prova automatica (usata per le build)
"""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
for p in (BASE / "backend", BASE / "ui", BASE / "windows", BASE):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("NEXUS_UI_DIR", str(BASE / "ui"))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

UDEV = ('echo \'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"\' '
        '> /etc/udev/rules.d/60-nexus-uinput.rules; echo uinput > /etc/modules-load.d/nexus-uinput.conf; '
        'modprobe uinput; udevadm control --reload-rules; udevadm trigger /dev/uinput; usermod -aG input "$1"')


CERTS = ("/etc/ssl/certs/ca-certificates.crt",            # Debian/Ubuntu/Mint, Arch
         "/etc/pki/tls/certs/ca-bundle.crt",              # Fedora/RHEL
         "/etc/ssl/ca-bundle.pem",                        # openSUSE
         "/etc/ssl/cert.pem")


def _certs():
    """Il Python incluso cerca i certificati HTTPS dove li mette Ubuntu: sulle altre distro HTTPS fallirebbe.
    Si usano quelli del sistema, altrimenti quelli di certifi inclusi nell'app."""
    if os.environ.get("SSL_CERT_FILE"):
        return
    for c in CERTS:
        if os.path.exists(c):
            os.environ["SSL_CERT_FILE"] = c
            return
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass


CHILD_ENV = None


def _system_ui():
    """Su KDE Wayland il notch vero (in alto, fuori dalla barra delle applicazioni) richiede il layer-shell,
    che il Qt incluso nell'AppImage non può caricare: l'interfaccia parte allora con il Python e il PySide6
    del sistema (come l'installazione da script). Ritorna il comando, oppure None se non si può."""
    if os.environ.get("XDG_SESSION_TYPE") != "wayland" or os.environ.get("NEXUS_NO_LAYERSHELL") == "1":
        return None
    if not Path("/usr/lib/qt6/qml/org/kde/layershell/qmldir").exists():
        return None
    for py in ("/usr/bin/python3", "/usr/bin/python"):
        if not os.path.exists(py):
            continue
        try:
            r = subprocess.run([py, "-c", "import PySide6.QtQml, PySide6.QtNetwork"], env=CHILD_ENV,
                               capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return [py, str(BASE / "ui" / "app.py")]
    return None


def _clean_children():
    """I programmi aperti da NEXUS (browser, Dolphin, terminale…) non devono ereditare le librerie
    e i percorsi Qt/Python dell'AppImage, altrimenti si chiudono o si aprono male."""
    if not getattr(sys, "frozen", False):
        return
    env = dict(os.environ)
    for k in ("LD_LIBRARY_PATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH",
              "PYTHONHOME", "PYTHONPATH", "GST_PLUGIN_SYSTEM_PATH", "GIO_MODULE_DIR",
              "QT_WAYLAND_SHELL_INTEGRATION", "NEXUS_UI_DIR", "QT_QUICK_CONTROLS_STYLE", "APPDIR", "APPIMAGE", "OWD", "ARGV0"):
        orig = env.pop(k + "_ORIG", None)
        env.pop(k, None)
        if orig:
            env[k] = orig
    global CHILD_ENV
    CHILD_ENV = env
    init = subprocess.Popen.__init__

    def patched(self, *a, **kw):
        if kw.get("env") is None:
            kw["env"] = env
        init(self, *a, **kw)
    subprocess.Popen.__init__ = patched


def _log_to_file():
    from nexus.config import DATA
    DATA.mkdir(parents=True, exist_ok=True)
    log = DATA / "nexus.log"
    if log.exists() and log.stat().st_size > 2_000_000:
        log.replace(DATA / "nexus.old.log")
    f = open(log, "a", encoding="utf-8", buffering=1)
    f.write(f"\n===== NEXUS avviato {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    if not sys.stdout or not sys.stdout.isatty():
        sys.stdout = sys.stderr = f


def _single_instance():
    import fcntl
    from nexus.config import DATA
    DATA.mkdir(parents=True, exist_ok=True)
    global _lock
    _lock = open(DATA / "nexus.lock", "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _desktop_integration():
    """Voce nel menu delle app e avvio all'accesso, puntati al file .AppImage (aggiornati se lo sposti)."""
    app = os.environ.get("APPIMAGE")
    if not app:
        return
    icon_dir = Path.home() / ".local/share/icons/hicolor/256x256/apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon = icon_dir / "nexus-assistant.png"
    src = BASE / "nexus.png"
    if src.exists() and (not icon.exists() or icon.stat().st_size != src.stat().st_size):
        icon.write_bytes(src.read_bytes())
    entry = f"""[Desktop Entry]
Type=Application
Name=NEXUS
Comment=Assistente vocale con notch e casco robot
Exec="{app}"
Icon=nexus-assistant
Terminal=false
Categories=Utility;
"""
    menu = Path.home() / ".local/share/applications/nexus-assistant.desktop"
    menu.parent.mkdir(parents=True, exist_ok=True)
    if not menu.exists() or menu.read_text() != entry:
        menu.write_text(entry)
    auto = Path.home() / ".config/autostart/nexus-assistant.desktop"
    from nexus.config import DATA
    if not (DATA / "no-autostart").exists():
        auto.parent.mkdir(parents=True, exist_ok=True)
        a = entry + "X-GNOME-Autostart-enabled=true\n"
        if not auto.exists() or auto.read_text() != a:
            auto.write_text(a)


def _permessi():
    if os.access("/dev/uinput", os.W_OK):
        print("Mouse e tastiera virtuali: permesso già presente.")
        return 0
    user = os.environ.get("USER") or os.getlogin()
    print("Chiedo la password di amministratore per dare a NEXUS mouse e tastiera virtuali…")
    r = subprocess.run(["pkexec", "sh", "-c", UDEV, "sh", user])
    if r.returncode == 0:
        print("Fatto. Esci e rientra (o riavvia) perché valga il gruppo 'input'.")
    return r.returncode


def main():
    if getattr(sys, "frozen", False):
        _certs()
    if "--selftest-ui" in sys.argv:
        import selftest
        selftest.ui_main()
    if "--selftest" in sys.argv:
        import selftest
        sys.exit(selftest.main())
    if "--permessi" in sys.argv:
        sys.exit(_permessi())
    _clean_children()
    if getattr(sys, "frozen", False):
        _log_to_file()
    if not _single_instance():
        print("NEXUS è già aperto.")
        return
    try:
        _desktop_integration()
    except OSError as e:
        print("integrazione col desktop non riuscita:", e)
    from nexus.main import Nexus

    def backend():
        try:
            Nexus().start()
        except Exception:
            import traceback
            traceback.print_exc()
    threading.Thread(target=backend, daemon=True, name="backend").start()
    cmd = _system_ui() if getattr(sys, "frozen", False) else None
    if cmd:
        print("interfaccia con il Qt di sistema (layer-shell):", cmd[0])
        env = dict(CHILD_ENV, NEXUS_UI_DIR=str(BASE / "ui"))
        r = subprocess.run(cmd, env=env)
        if r.returncode == 0:
            os._exit(0)                                          # "Esci da NEXUS"
        print("interfaccia di sistema chiusa con codice", r.returncode, "- uso quella inclusa")
    if os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("DISPLAY") and getattr(sys, "frozen", False):
        # senza layer-shell su Wayland le finestre non si possono mettere in alto né togliere dalla barra:
        # con XWayland sì (notch in alto, fuori dalla barra delle applicazioni)
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    import app                                                   # ui/app.py
    app.main()


if __name__ == "__main__":
    main()
