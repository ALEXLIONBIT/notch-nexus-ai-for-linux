"""Desktop virtuali (KDE Plasma, Cinnamon/Mint e gli altri X11): ogni compito di NEXUS ricorda il desktop dove
l'hai chiesto. Così puoi dare un compito sul desktop 1, passare al 2 e chiederne un altro: le finestre che apre
il primo compito restano sul desktop 1, e mouse/schermo li usa solo quando quel desktop è davanti a te.
Dove i desktop virtuali non si possono leggere (Windows, GNOME Wayland) è come se ce ne fosse uno solo.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

from .osys import IS_WIN

QDBUS = "qdbus6"
_cache = {"t": 0.0, "num": 0, "count": 1}
_lock = threading.Lock()


def _kde():
    return not IS_WIN and bool(shutil.which(QDBUS)) and "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


def _x11():
    return not IS_WIN and bool(os.environ.get("DISPLAY")) and os.environ.get("XDG_SESSION_TYPE") != "wayland" \
        and bool(shutil.which("xprop"))


def _read():
    """(desktop attuale 1..n, quanti desktop); (0, 1) se non si sa."""
    if not IS_WIN and not os.environ.get("XDG_CURRENT_DESKTOP"):
        from .osys import fix_gui_env
        fix_gui_env()                                  # servizio partito prima della sessione grafica
    try:
        if _kde():
            num = subprocess.run([QDBUS, "org.kde.KWin", "/KWin", "org.kde.KWin.currentDesktop"],
                                 capture_output=True, text=True, timeout=3).stdout.strip()
            cnt = subprocess.run([QDBUS, "org.kde.KWin", "/VirtualDesktopManager", "org.freedesktop.DBus.Properties.Get",
                                  "org.kde.KWin.VirtualDesktopManager", "count"],
                                 capture_output=True, text=True, timeout=3).stdout.strip()
            return int(num), int(cnt) if cnt.isdigit() else 1
        if _x11():
            out = subprocess.run(["xprop", "-root", "_NET_CURRENT_DESKTOP", "_NET_NUMBER_OF_DESKTOPS"],
                                 capture_output=True, text=True, timeout=3).stdout
            vals = re.findall(r"=\s*(\d+)", out)
            if vals:
                return int(vals[0]) + 1, int(vals[1]) if len(vals) > 1 else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return 0, 1


def current():
    """Numero del desktop davanti all'utente (1, 2, 3…); 0 = non si sa (si comporta come un desktop solo)."""
    with _lock:
        if time.time() - _cache["t"] > 0.3:
            _cache["num"], _cache["count"] = _read()
            _cache["t"] = time.time()
        return _cache["num"]


def count():
    current()
    return _cache["count"]


def is_current(num):
    return not num or current() in (0, num)


def label(num):
    return f"desktop {num}" if num else ""


# ---------------------------------------------------------------- finestre nuove sul desktop del compito

_KWIN_FOLLOW = r"""
var NUM = %(num)d, HINTS = %(hints)s, moved = 0, cls = null;
function hay(w) { return (String(w.resourceClass) + " " + String(w.resourceName) + " " + String(w.desktopFileName || "")
                  + " " + String(w.caption)).toLowerCase(); }
function wanted(w) {
  if (!w.normalWindow || w.skipTaskbar || w.resourceClass === "nexus-ui" || moved >= 4) return false;
  if (cls !== null) return w.resourceClass === cls;
  if (!HINTS.length) return true;
  var h = hay(w);
  for (var i = 0; i < HINTS.length; i++) if (h.indexOf(HINTS[i]) >= 0) return true;
  return false;
}
if (typeof workspace.windowAdded !== "undefined") {
  var target = workspace.desktops[NUM - 1];
  if (target) workspace.windowAdded.connect(function (w) {
    if (!wanted(w)) return;
    cls = w.resourceClass; moved++; w.desktops = [target];
  });
} else {
  workspace.clientAdded.connect(function (c) {
    if (!wanted(c)) return;
    cls = c.resourceClass; moved++; c.desktop = NUM;
  });
}
"""


def follow(num, hints=(), seconds=15):
    """Per `seconds` secondi le finestre nuove dell'app appena aperta (riconosciuta dai `hints`) vanno sul desktop
    `num` invece che su quello dove sei adesso. Non fa niente se c'è un desktop solo."""
    if not num or count() < 2:
        return
    hints = [h.lower() for h in hints if h and len(h) >= 3]
    if _kde():
        threading.Thread(target=_follow_kwin, args=(num, hints, seconds), daemon=True).start()
    elif _x11() and shutil.which("wmctrl"):
        threading.Thread(target=_follow_wmctrl, args=(num, hints, seconds), daemon=True).start()


def _follow_kwin(num, hints, seconds):
    from .config import CACHE
    tag = "NEXUSFOLLOW" + uuid.uuid4().hex[:8]
    path = CACHE / f"{tag}.js"
    path.write_text(_KWIN_FOLLOW % {"num": num, "hints": json.dumps(hints)})
    try:
        sid = subprocess.run([QDBUS, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript", str(path), tag],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if sid.lstrip("-").isdigit() and int(sid) >= 0:
            subprocess.run([QDBUS, "org.kde.KWin", f"/Scripting/Script{sid}", "org.kde.kwin.Script.run"],
                           capture_output=True, timeout=10)
            time.sleep(seconds)
    except (OSError, subprocess.SubprocessError) as e:
        print("finestre sul desktop del compito:", e)
    finally:
        subprocess.run([QDBUS, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", tag],
                       capture_output=True, timeout=10)
        path.unlink(missing_ok=True)


def _wm_windows():
    out = subprocess.run(["wmctrl", "-lx"], capture_output=True, text=True, timeout=5).stdout
    res = {}
    for line in out.splitlines():
        p = line.split(None, 4)
        if len(p) >= 3 and p[1] != "-1":
            res[p[0]] = (p[2] + " " + (p[4] if len(p) > 4 else "")).lower()
    return res


def _follow_wmctrl(num, hints, seconds):
    try:
        before = set(_wm_windows())
        end, moved, cls = time.time() + seconds, 0, None
        while time.time() < end and moved < 4:
            time.sleep(0.5)
            for wid, hay in _wm_windows().items():
                if wid in before:
                    continue
                before.add(wid)
                klass = hay.split()[0]
                if (cls and klass != cls) or (not cls and hints and not any(h in hay for h in hints)):
                    continue
                cls = klass
                moved += 1
                subprocess.run(["wmctrl", "-i", "-r", wid, "-t", str(num - 1)], capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        print("finestre sul desktop del compito:", e)
