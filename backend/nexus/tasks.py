"""Più compiti insieme: "Ehi Nexus, …" mentre NEXUS sta già lavorando avvia un altro compito in parallelo.

- Ogni compito ricorda il desktop virtuale dove l'hai chiesto (desktops.py) e ha la sua memoria per desktop.
- Le "mani" (schermo, mouse, tastiera, browser pilotato, installazioni) le usa un compito alla volta:
  se servono a un compito mentre le sta usando un altro, aspetta che l'altro finisca.
  Schermo e mouse servono sul desktop del compito: se sei su un altro desktop aspetta che torni lì.
- "Ehi Nexus basta" / "stop" / "zitto" ferma la voce e il compito del desktop dove sei
  ("basta tutto" li ferma tutti).
"""
import re
import threading
import time
import uuid

from . import desktops
from .providers import Cancelled

MAX_TASKS = 4

# strumenti che guardano o toccano lo schermo: servono sul desktop del compito
SCREEN = {"look_screen", "read_screen_text", "click", "click_text", "move_mouse", "drag", "scroll", "press_keys",
          "type_text", "place_window", "split_screen", "window_action"}
# strumenti che un compito alla volta (oltre allo schermo): installazioni e TV
EXCLUSIVE = SCREEN | {"install_app", "steam_game", "cast_screen", "stop_cast"}
# strumenti che aprono finestre: le finestre nuove vanno sul desktop del compito
OPENERS = {"open_app", "open_url", "web_search", "open_folder", "open_file", "steam_game"}
BROWSERS = ["firefox", "chrom", "brave", "edge", "vivaldi", "opera", "librewolf", "zen", "falkon", "epiphany"]
FILE_MANAGERS = ["dolphin", "nautilus", "nemo", "thunar", "caja", "pcmanfm", "files", "explorer"]

STOP_WORDS = {"basta", "stop", "fermati", "ferma", "fermo", "fermate", "smettila", "smetti", "zitto", "zitta",
              "silenzio", "annulla", "finiscila", "taci", "shh", "sst", "cancel", "enough", "quiet"}
FILLER = {"ok", "okay", "dai", "ehi", "hey", "no", "ti", "prego", "per", "favore", "stai", "cosi", "così", "ora",
          "adesso", "subito", "grazie", "di", "parlare", "fare", "quello", "questo", "lascia", "stare", "perdere",
          "tutto", "tutti", "tutte", "compito", "compiti", "please", "now", "it", "that", "everything", "all", "e",
          "pure", "allora", "va", "bene", "la", "il", "lo"}
ALL = re.compile(r"\b(tutt[oie]|everything|all)\b", re.I)


def is_stop(text, name=""):
    """True se la frase è solo un "basta" ("basta", "ok stop", "stai zitto", "basta così", "ferma tutto"),
    non un comando vero ("ferma la musica" va al cervello, che mette in pausa la musica)."""
    words = re.findall(r"[a-zàèéìòù]+", (text or "").lower())
    if not words or len(words) > 6:
        return False
    skip = set(re.findall(r"[a-zàèéìòù]+", (name or "").lower()))
    if not any(w in STOP_WORDS for w in words):
        return False
    return all(w in STOP_WORDS or w in FILLER or w in skip for w in words)


def needs_hands(name, registry):
    return name in EXCLUSIVE or name.startswith("browser_") or \
        (name in ("open_url", "web_search") and "browser_navigate" in registry)


def window_hints(name, args, cfg):
    """Parole per riconoscere la finestra che sta per aprire il tool (vedi desktops.follow)."""
    if name == "open_app":
        from .tools.apps import find_app
        app = find_app(str(args.get("name", "")), cfg) or {}
        words = re.findall(r"[a-z0-9]+", (app.get("name", "") + " " + str(app.get("id", "")).split("/")[-1]).lower())
        return [w for w in words if w not in ("desktop", "org", "com", "kde", "gnome", "app")] or \
            re.findall(r"[a-z0-9]+", str(args.get("name", "")).lower())
    if name in ("open_url", "web_search"):
        b = (cfg.get("browser") or "").lower()
        return [w for w in BROWSERS if w in b] or BROWSERS
    if name == "open_folder":
        return FILE_MANAGERS
    if name == "steam_game":
        return ["steam"]
    return []


class Task:
    """Un compito: la frase, il desktop dove è stato chiesto, lo stato. `cancelled` lo ferma al prossimo passo."""

    def __init__(self, text, desktop=0, attachments=None):
        self.id = uuid.uuid4().hex[:6]
        self.text = text or ""
        self.desktop = desktop
        self.attachments = list(attachments or [])
        self.cancelled = False
        self.started = time.time()
        self.step = ""
        self.waiting = ""
        self.listening = False
        self.log_steps = []
        self.ctx = None

    def info(self):
        return {"id": self.id, "text": self.text[:90], "desktop": self.desktop, "step": self.step,
                "waiting": self.waiting}


class Hands:
    """Schermo/mouse/tastiera/browser: un compito alla volta. Chi li prende li tiene fino alla fine del compito,
    così un altro compito non clicca in mezzo ai suoi passi. Se il compito che li tiene aspetta che torni sul
    suo desktop, li lascia: intanto li può usare il compito del desktop dove sei."""

    def __init__(self):
        self.cv = threading.Condition()
        self.owner = None

    def acquire(self, task, need_desktop, on_wait=lambda kind, other: None):
        told = None
        while True:
            if task.cancelled:
                raise Cancelled()
            visible = not need_desktop or desktops.is_current(task.desktop)
            with self.cv:
                if visible and self.owner in (None, task):
                    self.owner = task
                    task.waiting = ""
                    return
                if not visible and self.owner is task:
                    self.owner = None                      # aspetta il suo desktop: lascia le mani agli altri
                    self.cv.notify_all()
                other = self.owner
                kind = "desktop" if not visible else "other"
                if told != kind:
                    told = kind
                    task.waiting = kind
                    threading.Thread(target=on_wait, args=(kind, other), daemon=True).start()
                self.cv.wait(0.4)

    def release(self, task):
        with self.cv:
            if self.owner is task:
                self.owner = None
                self.cv.notify_all()
