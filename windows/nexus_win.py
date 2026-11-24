"""NEXUS per Windows: backend e interfaccia nello stesso programma (NEXUS.exe).

  NEXUS.exe              avvia l'assistente (una sola copia alla volta)
  NEXUS.exe --selftest   prova automatica di tutti i pezzi (usata per le build)
"""
import os
import sys
import threading
import time
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
SRC = BASE if getattr(sys, "frozen", False) else BASE
for p in (SRC / "backend", SRC / "ui", SRC):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("NEXUS_UI_DIR", str(SRC / "ui"))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def _log_to_file():
    """L'app non ha console: tutto quello che stamperebbe finisce in %LOCALAPPDATA%\\NEXUS\\nexus.log."""
    from nexus.config import DATA
    DATA.mkdir(parents=True, exist_ok=True)
    log = DATA / "nexus.log"
    if log.exists() and log.stat().st_size > 2_000_000:
        log.replace(DATA / "nexus.old.log")
    f = open(log, "a", encoding="utf-8", buffering=1)
    f.write(f"\n===== NEXUS avviato {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    sys.stdout = sys.stderr = f


def _single_instance():
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\NEXUS-assistant")
    return ctypes.windll.kernel32.GetLastError() != 183          # ERROR_ALREADY_EXISTS


def main():
    if "--selftest-ui" in sys.argv:
        import selftest
        selftest.ui_main()
    if "--selftest" in sys.argv:
        import selftest
        sys.exit(selftest.main())
    if sys.stdout is None or getattr(sys, "frozen", False):
        _log_to_file()
    if not _single_instance():
        print("NEXUS è già aperto.")
        return
    from nexus.main import Nexus

    def backend():
        try:
            Nexus().start()
        except Exception:
            import traceback
            traceback.print_exc()
    threading.Thread(target=backend, daemon=True, name="backend").start()
    import app                                                   # ui/app.py
    app.main()


if __name__ == "__main__":
    main()
