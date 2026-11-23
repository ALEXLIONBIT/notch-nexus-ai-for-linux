"""Mouse e tastiera su Wayland con dispositivi virtuali uinput (python-evdev).

Il mouse è una "tavoletta" a coordinate assolute: punta esattamente dove serve,
senza accelerazione e con qualsiasi scala di KDE. Coordinate dei tool: 0-1000
rispetto allo screenshot (0,0 = alto a sinistra, 1000,1000 = basso a destra).
Il testo passa dagli appunti (wl-copy + Ctrl+V) così gli accenti funzionano con la tastiera italiana.
"""
import subprocess
import threading
import time

from evdev import UInput, AbsInfo, ecodes as e

from . import tool
from .screen import screenshot, ocr, find_text

_lock = threading.Lock()
_mouse = _kbd = None
_size = (3840, 2400)        # aggiornato a ogni screenshot

KEYS = {
    "ctrl": e.KEY_LEFTCTRL, "control": e.KEY_LEFTCTRL, "shift": e.KEY_LEFTSHIFT, "alt": e.KEY_LEFTALT,
    "altgr": e.KEY_RIGHTALT, "super": e.KEY_LEFTMETA, "meta": e.KEY_LEFTMETA, "win": e.KEY_LEFTMETA,
    "enter": e.KEY_ENTER, "invio": e.KEY_ENTER, "esc": e.KEY_ESC, "escape": e.KEY_ESC, "tab": e.KEY_TAB,
    "space": e.KEY_SPACE, "spazio": e.KEY_SPACE, "backspace": e.KEY_BACKSPACE, "delete": e.KEY_DELETE,
    "canc": e.KEY_DELETE, "up": e.KEY_UP, "su": e.KEY_UP, "down": e.KEY_DOWN, "giu": e.KEY_DOWN,
    "left": e.KEY_LEFT, "sinistra": e.KEY_LEFT, "right": e.KEY_RIGHT, "destra": e.KEY_RIGHT,
    "home": e.KEY_HOME, "end": e.KEY_END, "pageup": e.KEY_PAGEUP, "pagedown": e.KEY_PAGEDOWN,
    "printscreen": e.KEY_SYSRQ, "volumeup": e.KEY_VOLUMEUP, "volumedown": e.KEY_VOLUMEDOWN,
    "mute": e.KEY_MUTE, "playpause": e.KEY_PLAYPAUSE,
    **{f"f{i}": getattr(e, f"KEY_F{i}") for i in range(1, 13)},
    **{c: getattr(e, f"KEY_{c.upper()}") for c in "abcdefghijklmnopqrstuvwxyz0123456789"},
}
BUTTONS = {"left": e.BTN_LEFT, "sinistro": e.BTN_LEFT, "right": e.BTN_RIGHT, "destro": e.BTN_RIGHT,
           "middle": e.BTN_MIDDLE, "centrale": e.BTN_MIDDLE}


def _devices():
    global _mouse, _kbd
    with _lock:
        if _mouse is None:
            _mouse = UInput({
                e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                e.EV_ABS: [(e.ABS_X, AbsInfo(0, 0, 65535, 0, 0, 0)), (e.ABS_Y, AbsInfo(0, 0, 65535, 0, 0, 0))],
                e.EV_REL: [e.REL_WHEEL, e.REL_HWHEEL],
            }, name="nexus-pointer", vendor=0x627, product=0x1, version=1)
            _kbd = UInput({e.EV_KEY: sorted(set(KEYS.values()))}, name="nexus-keyboard")
            time.sleep(0.8)      # il compositor deve "vedere" i nuovi dispositivi
    return _mouse, _kbd


def _norm(v):
    return max(0, min(1000, float(v))) / 1000 * 65535


def move(x, y):
    m, _ = _devices()
    m.write(e.EV_ABS, e.ABS_X, int(_norm(x)))
    m.write(e.EV_ABS, e.ABS_Y, int(_norm(y)))
    m.syn()
    time.sleep(0.05)


def click_btn(button="left", count=1):
    m, _ = _devices()
    b = BUTTONS.get(button, e.BTN_LEFT)
    for _ in range(count):
        m.write(e.EV_KEY, b, 1); m.syn(); time.sleep(0.03)
        m.write(e.EV_KEY, b, 0); m.syn(); time.sleep(0.07)


def press(combo):
    _, k = _devices()
    codes = []
    for name in combo.lower().replace(" ", "").split("+"):
        if name not in KEYS:
            raise ValueError(f"tasto sconosciuto: {name}")
        codes.append(KEYS[name])
    for c in codes:
        k.write(e.EV_KEY, c, 1); k.syn(); time.sleep(0.02)
    for c in reversed(codes):
        k.write(e.EV_KEY, c, 0); k.syn(); time.sleep(0.02)


def to_norm(px, py):
    """pixel dello screenshot → 0-1000"""
    return px / _size[0] * 1000, py / _size[1] * 1000


# ------------------------------------------------------------------ tool

@tool("click", "Clicca in un punto dello schermo. Coordinate 0-1000 rispetto allo screenshot "
      "(0,0 alto a sinistra; 1000,1000 basso a destra). Prima usa look_screen per sapere dove cliccare.",
      {"x": {"type": "number"}, "y": {"type": "number"},
       "button": {"type": "string", "enum": ["left", "right", "middle"]},
       "double": {"type": "boolean", "description": "doppio click"}}, ["x", "y"])
def click(ctx, x, y, button="left", double=False):
    ctx.step("🖱️", f"Clicco in ({int(x)}, {int(y)})")
    move(x, y)
    click_btn(button, 2 if double else 1)
    return f"Cliccato ({button}{', doppio' if double else ''}) in {int(x)},{int(y)}."


@tool("click_text", "Clicca su una scritta visibile sullo schermo (pulsante, link, voce di menu) "
      "cercandola con l'OCR. È il modo più preciso per cliccare testo.",
      {"text": {"type": "string"}, "button": {"type": "string", "enum": ["left", "right"]},
       "double": {"type": "boolean"}}, ["text"])
def click_text(ctx, text, button="left", double=False):
    global _size
    ctx.step("🎯", f"Cerco “{text}” sullo schermo")
    shot = screenshot()
    from PIL import Image
    _size = Image.open(shot).size
    pos, _score = find_text(ocr(shot), text)
    if not pos:
        return f"Non vedo “{text}” sullo schermo. Usa look_screen per guardare meglio."
    x, y = to_norm(pos[0], pos[1])
    ctx.step("🖱️", f"Clicco “{pos[2]}”")
    move(x, y)
    click_btn(button, 2 if double else 1)
    return f"Ho cliccato su “{pos[2]}”."


@tool("move_mouse", "Sposta il mouse in un punto (coordinate 0-1000), es. per passare sopra un menu.",
      {"x": {"type": "number"}, "y": {"type": "number"}}, ["x", "y"])
def move_mouse(ctx, x, y):
    ctx.step("🖱️", f"Sposto il mouse in ({int(x)}, {int(y)})")
    move(x, y)
    return "Mouse spostato."


@tool("drag", "Trascina col mouse da un punto a un altro (coordinate 0-1000).",
      {"x1": {"type": "number"}, "y1": {"type": "number"}, "x2": {"type": "number"}, "y2": {"type": "number"}},
      ["x1", "y1", "x2", "y2"])
def drag(ctx, x1, y1, x2, y2):
    ctx.step("🖱️", "Trascino")
    m, _ = _devices()
    move(x1, y1)
    m.write(e.EV_KEY, e.BTN_LEFT, 1); m.syn(); time.sleep(0.1)
    for i in range(1, 21):
        move(x1 + (x2 - x1) * i / 20, y1 + (y2 - y1) * i / 20)
        time.sleep(0.015)
    m.write(e.EV_KEY, e.BTN_LEFT, 0); m.syn()
    return "Trascinato."


@tool("scroll", "Scorre con la rotellina del mouse (sopra il punto dove si trova il mouse).",
      {"direction": {"type": "string", "enum": ["su", "giu", "sinistra", "destra"]},
       "amount": {"type": "integer", "description": "quanti scatti, default 5"}}, ["direction"])
def scroll(ctx, direction, amount=5):
    ctx.step("🖱️", f"Scorro {direction}")
    m, _ = _devices()
    axis = e.REL_HWHEEL if direction in ("sinistra", "destra") else e.REL_WHEEL
    sign = 1 if direction in ("su", "destra") else -1
    for _ in range(max(1, min(30, int(amount)))):
        m.write(e.EV_REL, axis, sign); m.syn(); time.sleep(0.03)
    return "Fatto."


@tool("press_keys", "Preme tasti o scorciatoie, es. 'enter', 'ctrl+t', 'alt+tab', 'ctrl+shift+t', 'super', 'f5'.",
      {"combo": {"type": "string"}}, ["combo"])
def press_keys(ctx, combo):
    ctx.step("⌨️", f"Premo {combo}")
    press(combo)
    return f"Premuto {combo}."


@tool("type_text", "Scrive del testo nella finestra attiva, dove c'è il cursore (prima clicca nel campo giusto).",
      {"text": {"type": "string"},
       "enter": {"type": "boolean", "description": "premi Invio alla fine"},
       "terminal": {"type": "boolean", "description": "true se stai scrivendo in un terminale"}}, ["text"])
def type_text(ctx, text, enter=False, terminal=False):
    ctx.step("⌨️", f"Scrivo “{text[:40]}”")
    subprocess.run(["wl-copy", "--", text], timeout=5)
    time.sleep(0.2)
    press("ctrl+shift+v" if terminal else "ctrl+v")
    if enter:
        time.sleep(0.15)
        press("enter")
    return "Testo scritto."
