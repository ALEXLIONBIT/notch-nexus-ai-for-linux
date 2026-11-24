"""Finestre su Windows (pywin32): elenco, trova per nome/titolo, sposta, massimizza, riduci, chiudi."""
import re
import time

import psutil
import win32api
import win32con
import win32gui
import win32process


def _norm(s):
    return re.sub(r"[^a-z0-9àèéìòù]+", " ", (s or "").lower()).strip()


def _visible_app_window(h):
    if not win32gui.IsWindowVisible(h) or not win32gui.GetWindowText(h):
        return False
    if win32gui.GetWindow(h, win32con.GW_OWNER):
        return False
    ex = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
    if ex & win32con.WS_EX_TOOLWINDOW:
        return False
    try:                                            # finestre "fantasma" delle app UWP sospese
        import ctypes
        cloaked = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return False
    except Exception:
        pass
    return win32gui.GetClassName(h) not in ("Progman", "WorkerW", "Shell_TrayWnd")


def list_windows():
    """[{hwnd, title, app, min, active}] dalla più in alto alla più in basso (ordine Z)."""
    active = win32gui.GetForegroundWindow()
    out = []

    def cb(h, _):
        if _visible_app_window(h):
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
                app = psutil.Process(pid).name().rsplit(".", 1)[0]
            except Exception:
                app = ""
            title = win32gui.GetWindowText(h)
            if app.lower() == "nexus" or title.startswith("NEXUS"):
                return True
            out.append({"hwnd": h, "title": title, "app": app,
                        "min": bool(win32gui.IsIconic(h)), "active": h == active})
        return True
    win32gui.EnumWindows(cb, None)
    return out


def find(q):
    words = _norm(q).split()
    for w in list_windows():                         # la prima è la più recente
        hay = " " + _norm(w["title"]) + " " + _norm(w["app"]) + " "
        if words and all(x in hay for x in words):
            return w
    return None


def _foreground(h):
    """Porta davanti una finestra (Windows lo permette solo se 'tocchi' un tasto prima)."""
    if win32gui.IsIconic(h):
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
    try:
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32gui.SetForegroundWindow(h)
    except Exception:
        win32gui.BringWindowToTop(h)


def workarea(h):
    """Area utile (senza barra delle applicazioni) del monitor dove sta la finestra."""
    mon = win32api.MonitorFromWindow(h, win32con.MONITOR_DEFAULTTONEAREST)
    left, top, right, bottom = win32api.GetMonitorInfo(mon)["Work"]
    return left, top, right - left, bottom - top


def place(w, frac):
    h = w["hwnd"]
    win32gui.ShowWindow(h, win32con.SW_RESTORE)
    time.sleep(0.05)
    ax, ay, aw, ah = workarea(h)
    fx, fy, fw, fh = frac
    win32gui.SetWindowPos(h, win32con.HWND_TOP, int(ax + aw * fx), int(ay + ah * fy), int(aw * fw), int(ah * fh),
                          win32con.SWP_SHOWWINDOW)
    _foreground(h)


def action(w, what):
    h = w["hwnd"]
    if what == "attiva":
        _foreground(h)
    elif what == "massimizza":
        win32gui.ShowWindow(h, win32con.SW_MAXIMIZE); _foreground(h)
    elif what == "riduci":
        win32gui.ShowWindow(h, win32con.SW_MINIMIZE)
    elif what == "ripristina":
        win32gui.ShowWindow(h, win32con.SW_RESTORE); _foreground(h)
    elif what == "schermo_intero":
        _foreground(h)
        from ._win_input import press
        press("f11")
    elif what == "chiudi":
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
