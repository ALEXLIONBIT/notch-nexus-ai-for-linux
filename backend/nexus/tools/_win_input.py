"""Mouse, tastiera e appunti su Windows (SendInput via ctypes, appunti con pywin32).

Stesse funzioni di basso livello di inputs.py su Linux: coordinate 0-1000 rispetto allo schermo principale
(quello dello screenshot), tasti per nome ("ctrl+t"), testo scritto come caratteri Unicode (accenti ok).
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
try:                                                    # pixel veri anche con lo schermo scalato al 125/150%
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
MOUSE = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x800, 0x1000
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _mouse(flags, data=0):
    return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, ctypes.c_ulong(data & 0xFFFFFFFF).value, flags, 0, 0))


def _key(vk=0, scan=0, flags=0):
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, flags, 0, 0))


VK = {
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "altgr": 0xA5, "super": 0x5B, "meta": 0x5B,
    "win": 0x5B, "windows": 0x5B, "enter": 0x0D, "invio": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
    "space": 0x20, "spazio": 0x20, "backspace": 0x08, "delete": 0x2E, "canc": 0x2E, "up": 0x26, "su": 0x26,
    "down": 0x28, "giu": 0x28, "left": 0x25, "sinistra": 0x25, "right": 0x27, "destra": 0x27, "home": 0x24,
    "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "printscreen": 0x2C, "volumeup": 0xAF, "volumedown": 0xAE,
    "mute": 0xAD, "playpause": 0xB3, "nextsong": 0xB0, "previoussong": 0xB1, "stop": 0xB2, "insert": 0x2D,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz0123456789"},
}
EXTENDED = {0x2E, 0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22, 0x2D, 0xA5, 0x5B}


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def move(x, y):
    w, h = screen_size()
    px = int(max(0, min(1000, float(x))) / 1000 * (w - 1))
    py = int(max(0, min(1000, float(y))) / 1000 * (h - 1))
    user32.SetCursorPos(px, py)
    time.sleep(0.05)


def button(name="left", down=True):
    d, u = MOUSE.get({"sinistro": "left", "destro": "right", "centrale": "middle"}.get(name, name), MOUSE["left"])
    _send(_mouse(d if down else u))


def click_btn(name="left", count=1):
    for _ in range(count):
        button(name, True); time.sleep(0.03)
        button(name, False); time.sleep(0.07)


def wheel(horizontal, sign):
    _send(_mouse(MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL, 120 * sign))


def press(combo):
    codes = []
    for name in combo.lower().replace(" ", "").split("+"):
        if name not in VK:
            raise ValueError(f"tasto sconosciuto: {name}")
        codes.append(VK[name])
    for c in codes:
        _send(_key(c, flags=KEYEVENTF_EXTENDEDKEY if c in EXTENDED else 0)); time.sleep(0.02)
    for c in reversed(codes):
        _send(_key(c, flags=(KEYEVENTF_EXTENDEDKEY if c in EXTENDED else 0) | KEYEVENTF_KEYUP)); time.sleep(0.02)


def type_unicode(text):
    """Scrive il testo carattere per carattere (accenti, emoji, qualsiasi layout di tastiera)."""
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            press("enter")
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):            # coppie surrogate per le emoji
            unit = int.from_bytes(data[i:i + 2], "little")
            _send(_key(scan=unit, flags=KEYEVENTF_UNICODE), _key(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        time.sleep(0.004)


def copy_to_clipboard(text):
    import win32clipboard
    for _ in range(10):                               # gli appunti possono essere occupati da un'altra app
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            time.sleep(0.05)
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def read_clipboard():
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return ""
    finally:
        win32clipboard.CloseClipboard()
