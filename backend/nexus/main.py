"""NEXUS backend: orecchie → cervello → mani → voce, e parla con la UI."""
import json
import os
import re
import subprocess
import time
import threading
import traceback
import uuid

from .config import Config
from .bus import Bus
from .osys import IS_WIN, FROZEN, PACKAGED, APPIMAGE, RELEASE_PREFIX
from . import desktops
from . import tasks as T

RELEASES = "https://api.github.com/repos/ALEXLIONBIT/notch-nexus-ai-for-linux/releases"

YES = re.compile(r"\b(s[iì]|ok|okay|certo|vai|procedi|conferm|fallo|esatto|d'accordo)\b", re.I)
NO = re.compile(r"\b(no|annulla|ferma|stop|lascia|non farlo|aspetta)\b", re.I)


IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
BLIND = {"click", "drag", "move_mouse", "type_text", "press_keys"}   # azioni alla cieca su uno schermo forse cambiato


class Ctx:
    """Quello che i tool vedono: passi nel notch, immagini, conferme. Con `task` è quello di un compito."""
    def __init__(self, nexus, task=None):
        self.n = nexus
        self.cfg = nexus.cfg
        self.task = task

    def step(self, icon, text):
        if self.task is not None:
            return self.n.task_step(self.task, icon, text)
        self.n.bus.emit("step", icon=icon, text=text)

    def image(self, path):
        self.n.bus.emit("image", path=path)

    def confirm(self, question):
        return self.n.confirm(question, self.task)

    def before_tool(self, name, args):
        return self.n.before_tool(self.task, name, args) if self.task is not None else ""


class Nexus:
    def __init__(self):
        self.cfg = Config()
        self.bus = Bus(self.cfg["host"], self.cfg["port"], self.on_command, self.on_connect)
        self.state = "loading"
        self.pending = {}
        self.deps_state = {"items": [], "checking": False, "working": "", "text": "", "pct": -1, "error": ""}
        self.deps_lock = threading.Lock()
        self.tasks = {}                        # compiti in corso (anche più di uno: vedi tasks.py)
        self.tasks_lock = threading.RLock()
        self.lanes = {}                        # memoria breve del cervello, una per desktop virtuale
        self.hands = T.Hands()                 # schermo/mouse/browser: un compito alla volta
        self.mic = threading.Lock()            # il microfono: un ascolto alla volta
        self.speech = threading.Lock()         # la voce: una risposta alla volta, le altre in coda
        self.speaking_task = None
        self.confirm_lock = threading.Lock()   # le domande sì/no: una alla volta
        self.chat_lock = threading.Lock()
        self.ears = self.voice = self.stt = self.brain = None
        self.chat = None                       # chat in corso (vedi chats.py)
        self.bmcp = None                       # Playwright MCP (browsermcp.py)
        self.bmcp_status = {"state": "off", "browser": "", "text": ""}

    # ---------- avvio ----------
    def start(self):
        if not IS_WIN:
            from .osys import fix_gui_env
            fix_gui_env()
        self.bus.start()
        self.set_state("loading", "Carico i moduli…")
        from .audio import Ears
        from .tts import Voice
        from .stt import Stt
        from .brain import Brain
        from .tools import Tools
        self.ears = Ears(self.cfg, self.bus, self.on_wake)
        self.voice = Voice(self.cfg, self.bus, self.ears)
        self.set_state("loading", "Carico il riconoscimento vocale…")
        self.stt = Stt(self.cfg, progress=lambda text, pct=-1: self.set_state("loading", text))
        self.brain = Brain(self.cfg, Tools(Ctx(self)), Ctx(self))
        if self.cfg.get("browser_mcp", True):
            threading.Thread(target=self.browser_start, daemon=True).start()
        self.ears.start()
        try:                                    # porta per telefono/tablet (cervello + immagini)
            from . import gateway
            gateway.start()
            gateway.Handler.status_cb = self.remote_status
            gateway.Handler.cfg = self.cfg
            from . import llamacpp
            llamacpp.on_status = lambda text: self.bus.emit("toast", text=text)
            gateway.Handler.apply_cb = lambda i: threading.Thread(target=self.deps_apply, args=(i,), daemon=True).start()
        except OSError as e:
            print("gateway non avviato:", e)
        threading.Thread(target=self.update_check, daemon=True).start()
        threading.Thread(target=self.deps_check, daemon=True).start()
        self.set_state("idle", self._idle_text())
        print("NEXUS pronto.")
        if not FROZEN:
            threading.Event().wait()          # nell'app Windows il backend gira in un thread e la UI tiene vivo il processo

    def _idle_text(self):
        w = ("Ehi " + (self.cfg.get("agent_name") or "Nexus")) if self.cfg["wake_word"] == "name" \
            else self.cfg["wake_word"].replace("_", " ").title()
        if self.ears and self.ears.stream is None:
            return "Nessun microfono: scrivimi"
        return f"Di' “{w}”" if self.ears and (self.ears.oww or self.ears.spotter) else "Clicca 🎤 per parlare"

    def set_state(self, state, detail=""):
        self.state, self.detail = state, detail
        self.bus.emit("state", state=state, detail=detail)

    def on_connect(self):
        if IS_WIN or PACKAGED:
            from . import __version__
            self.bus.emit("platform", os="windows" if IS_WIN else "linux", version=__version__)
        from .tools.apps import list_browsers
        from .providers import PRESETS
        self.bus.emit("browsers", list=list_browsers())
        self.bus.emit("presets", presets=PRESETS)
        self.bus.emit("config", config=self.cfg.public())
        self.bus.emit("state", state=self.state, detail=getattr(self, "detail", ""))
        self._emit_chat()
        self.bus.emit("browser_mcp", **self.bmcp_status)

    # ---------- comandi dalla UI ----------
    def on_command(self, msg):
        t = msg.get("type")
        if t == "listen":
            self.on_wake()
        elif t == "text" and (msg.get("text", "").strip() or msg.get("files")):
            self._spawn(msg.get("text", "").strip(), files=msg.get("files") or [])
        elif t == "task_stop":
            with self.tasks_lock:
                task = self.tasks.get(msg.get("id"))
            if task is not None:
                self.cancel_task(task)
                self._settle()
        elif t == "confirm":
            p = self.pending.get(msg.get("id"))
            if p and not p["ev"].is_set():
                p["ok"] = bool(msg.get("ok"))
                p["ev"].set()
        elif t == "stop":
            self.stop()
        elif t == "transcribe_file" and self.stt:     # per i test: trascrive un wav 16 kHz mono
            import time, wave
            import numpy as np
            with wave.open(msg["path"]) as w:
                audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            t0 = time.time()
            text = self.stt.transcribe(audio)
            self.bus.emit("stt_result", text=text, seconds=round(time.time() - t0, 2), device=self.stt.device)
        elif t == "config":
            self.apply_config(msg.get("config", {}))
        elif t == "update_check":
            threading.Thread(target=self.update_check, daemon=True).start()
            threading.Thread(target=self.deps_check, daemon=True).start()
        elif t == "deps_get":                         # interfaccia appena collegata: stato già pronto, se c'è
            if self.deps_state["items"] or self.deps_state["checking"]:
                self.bus.emit("deps_status", **self.deps_state)
            else:
                threading.Thread(target=self.deps_check, daemon=True).start()
        elif t == "deps_check":
            threading.Thread(target=self.deps_check, daemon=True).start()
        elif t == "deps_apply":
            threading.Thread(target=self.deps_apply, args=(msg.get("id", ""),), daemon=True).start()
        elif t == "browser_mcp":
            self.cfg["browser_mcp"] = bool(msg.get("on"))
            self.cfg.save()
            self.bus.emit("config", config=self.cfg.public())
            threading.Thread(target=self.browser_start if msg.get("on") else self.browser_stop, daemon=True).start()
        elif t == "wake_record":
            threading.Thread(target=self.wake_record, daemon=True).start()
        elif t == "wake_clear":
            sp = self.ears.spotter if self.ears else None
            if sp is not None and sp.voice is not None:
                sp.voice.clear()
            else:
                from .wakevoice import VoiceMatcher
                VoiceMatcher().clear()
            self.bus.emit("wake_voice", ready=False, step=0, text="Registrazione cancellata.")
        elif t == "wake_voice_status":
            from .wakevoice import DIR
            self.bus.emit("wake_voice", ready=len(list(DIR.glob("clip*.npy"))) >= 2 if DIR.exists() else False, step=0, text="")
        elif t == "perms_status":
            from . import perms
            self.bus.emit("perms", **perms.status(self.ears), text="")
        elif t == "perms_grant":
            def grant():
                from . import perms
                ok, text = perms.grant_uinput()
                self.bus.emit("perms", **perms.status(self.ears), text=text, ok=ok)
            threading.Thread(target=grant, daemon=True).start()
        elif t == "restart":
            threading.Thread(target=self.restart, daemon=True).start()
        elif t == "update_apply":
            threading.Thread(target=self.update_apply, daemon=True).start()
        elif t == "tailscale_status":
            from . import tailnet
            threading.Thread(target=lambda: self.bus.emit("tailscale", **tailnet.status()), daemon=True).start()
        elif t == "tailscale_connect":
            from . import tailnet
            threading.Thread(target=tailnet.connect, args=(lambda d: self.bus.emit("tailscale", **d),), daemon=True).start()
        elif t == "setup_choice":
            threading.Thread(target=self.setup_choice, args=(msg.get("choice"),), daemon=True).start()
        elif t in ("chats_list", "chat_open", "chat_new", "chat_delete", "chat_rename"):
            self.chat_command(t, msg)
        elif t in ("models_installed", "models_search", "model_pull", "model_delete", "model_use"):
            threading.Thread(target=self.models_command, args=(t, msg), daemon=True).start()
        elif t in ("provider_save", "provider_delete", "provider_models", "provider_test"):
            threading.Thread(target=self.provider_command, args=(t, msg), daemon=True).start()

    def stop(self):
        """Tasto Ferma: ferma TUTTO subito (voce, ascolto, tutti i compiti, conferme)."""
        self.stop_command("tutto")
        if self.ears:
            self.ears.cancel()
        for p in list(self.pending.values()):
            p["ok"] = False
            p["ev"].set()

    def stop_command(self, text="", skip=None):
        """"Ehi Nexus basta": zitto subito e ferma il compito del desktop dove sei
        (se stava solo parlando, smette di parlare); "basta tutto" ferma tutti i compiti."""
        everything = bool(T.ALL.search(text or ""))
        talking = self.speaking_task if self.speech.locked() else None
        if self.voice:
            self.voice.stop()
        self.bus.emit("say", text="", dur=0, first=True, last=True)
        cur = desktops.current()
        with self.tasks_lock:
            live = [t for t in self.tasks.values() if not t.cancelled and t is not skip]
        if everything:
            targets = live
        else:
            targets = [t for t in live if not t.desktop or not cur or t.desktop == cur]
            if talking is not None and talking in live and talking not in targets:
                targets.append(talking)
            if not targets and talking is None:
                targets = live[-1:]                   # niente qui e non parlava: il compito più recente
        for t in targets:
            self.cancel_task(t)
        print("basta:", ", ".join(f"«{t.text[:40]}»" for t in targets) or "solo la voce")
        self._settle()

    def cancel_task(self, task):
        task.cancelled = True
        for p in list(self.pending.values()):
            if p.get("task") is task:
                p["ok"] = False
                p["ev"].set()
        if task.listening and self.ears:
            self.ears.cancel()
        if self.speaking_task is task and self.voice:
            self.voice.stop()
        self.task_step(task, "■", "Fermato")

    def apply_config(self, new):
        old = dict(self.cfg)
        for k, v in new.items():
            if k == "model":                       # vecchia UI: cambia il modello del provider attivo
                self.cfg.active_provider()["model"] = v
            elif k in self.cfg.public() and k != "providers":
                self.cfg[k] = v
        self.cfg.save()
        if self.stt and (old["stt_mode"] != self.cfg["stt_mode"] or old["stt_model"] != self.cfg["stt_model"]):
            self.stt.reset()
        if self.voice and old["voice"] != self.cfg["voice"]:
            self.voice.load()
        if self.ears and old["wake_word"] != self.cfg["wake_word"]:
            self.ears.load_wakeword()
        if old.get("browser") != self.cfg.get("browser") and self.bmcp is not None:
            threading.Thread(target=self.browser_start, daemon=True).start()     # altro browser: riparte con quello
        if old.get("agent_name") != self.cfg.get("agent_name"):
            for lane in self.lanes.values():   # nuovo nome: la memoria breve riparte
                lane["history"] = []
        self.bus.emit("config", config=self.cfg.public())
        if self.state == "idle":
            self.set_state("idle", self._idle_text())

    def quick_command(self, text):
        t = text.lower()
        if re.search(r"auto ?mode|modalit[aà] auto|automatic", t):
            self.cfg["auto_mode"] = True
        elif re.search(r"manual|modalit[aà] manual", t) and len(t) < 60:
            self.cfg["auto_mode"] = False
        else:
            return None
        self.cfg.save()
        self.bus.emit("config", config=self.cfg.public())
        return "Automode attivo: faccio tutto senza chiederti conferma." if self.cfg["auto_mode"] \
            else "Modalità manuale: ti chiederò conferma prima delle cose importanti."

    # ---------- primo avvio (Windows e AppImage): dove gira il cervello ----------
    def setup_choice(self, choice):
        """'local' = installa Ollama (winget) e scarica un modello adatto al PC; 'provider' = lo sceglie l'utente."""
        def status(text, pct=-1, done=False, error=""):
            self.bus.emit("setup_status", text=text, pct=pct, done=done, error=error)
        if choice != "local":
            self.cfg["setup_done"] = True
            self.cfg.save()
            self.bus.emit("config", config=self.cfg.public())
            status("", done=True)
            return
        try:
            from . import winsetup
            model = winsetup.install_local_brain(status)
            p = self.cfg.get_provider("local")
            if p is None:
                from .providers import DEFAULT_PROVIDER
                p = dict(DEFAULT_PROVIDER)
                self.cfg["providers"].append(p)
            p["model"] = model
            self.cfg["provider"] = "local"
            self.cfg["setup_done"] = True
            self.cfg.save()
            self.bus.emit("config", config=self.cfg.public())
            status(f"Fatto! Il cervello {model} gira su questo PC.", 100, done=True)
        except Exception as e:
            traceback.print_exc()
            status("", error=str(e)[:200])

    # ---------- aggiornamenti (git dal sorgente, release GitHub per Windows e AppImage) ----------
    def _win_latest(self):
        import urllib.request
        req = urllib.request.Request(RELEASES + "?per_page=30", headers={"User-Agent": "nexus-assistant"})
        rels = json.loads(urllib.request.urlopen(req, timeout=20).read())
        rels = [r for r in rels if r.get("tag_name", "").startswith(RELEASE_PREFIX) and not r.get("draft")]
        return rels[0] if rels else None

    def _win_update_check(self):
        from . import __version__

        def ver(v):
            return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))
        try:
            r = self._win_latest()
            latest = r["tag_name"].removeprefix(RELEASE_PREFIX) if r else __version__
            newer = ver(latest) > ver(__version__)
            news = [l.strip("-* ").strip() for l in (r.get("body") or "").splitlines() if l.strip().startswith(("-", "*"))][:6] if newer else []
            self._update_emit(current=__version__, behind=1 if newer else 0,
                          news=[f"Versione {latest}"] + ["• " + n for n in news] if newer else [], error="")
        except Exception as e:
            self._update_emit(current=__version__, behind=0, news=[], error=str(e)[:160])

    def _win_update_apply(self):
        """Scarica l'installer nuovo, lo avvia in silenzio e chiude NEXUS (l'installer lo riapre)."""
        import os
        import urllib.request
        from .config import CACHE
        self._update_emit(current="", behind=0, news=[], error="", working=True)
        try:
            r = self._win_latest()
            ext = ".exe" if IS_WIN else ".appimage"
            asset = next(a for a in r["assets"] if a["name"].lower().endswith(ext))
            dest = CACHE / asset["name"]
            req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "nexus-assistant"})
            with urllib.request.urlopen(req, timeout=60) as src, open(dest, "wb") as f:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        except Exception as e:
            self._update_emit(current="", behind=0, news=[], error="download: " + str(e)[:150])
            return
        self._update_emit(current="", behind=0, news=[], error="", restarting=True)
        if not IS_WIN:
            # AppImage: sostituisce il file con quello nuovo e lo riapre
            import shutil
            target = APPIMAGE or str(dest)
            os.chmod(dest, 0o755)
            if APPIMAGE:
                shutil.move(str(dest), APPIMAGE + ".new")
                os.replace(APPIMAGE + ".new", APPIMAGE)
            self._relaunch(["sh", "-c", f'sleep 2; exec "{target}"'])
        subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & "{dest}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
                         creationflags=0x08000000, close_fds=True)
        time.sleep(0.5)
        os._exit(0)

    def _relaunch(self, cmd):
        """Riapre NEXUS con cmd (lanciato a parte) e chiude questo: anche l'interfaccia, se è un processo figlio
        (AppImage con il Qt di sistema), altrimenti resterebbe aperta una seconda interfaccia."""
        import signal
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        if not IS_WIN:
            try:
                os.killpg(os.getpgrp(), signal.SIGTERM)
            except OSError:
                pass
        os._exit(0)

    def restart(self):
        """Personalizza → Aggiornamenti → Riavvia: chiude e riapre tutto NEXUS."""
        import sys
        self._update_emit(current="", behind=0, news=[], error="", restarting=True)
        time.sleep(0.3)
        if IS_WIN and FROZEN:
            subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & start "" "{sys.executable}"',
                             creationflags=0x08000000, close_fds=True)
            time.sleep(0.5)
            os._exit(0)
        if APPIMAGE:
            self._relaunch(["sh", "-c", f'sleep 2; exec "{APPIMAGE}"'])
        from .config import ROOT
        subprocess.Popen(["sh", "-c", "sleep 1; systemctl --user --no-block restart nexus-backend nexus-ui || "
                          f"(pkill -f 'nexus.main'; pkill -f 'ui/app.py'; setsid {ROOT}/scripts/nexus >/dev/null 2>&1 &)"],
                         start_new_session=True)

    def _update_emit(self, **kw):
        if kw.get("current") or kw.get("error"):
            self.update_state = dict(kw)
        self.bus.emit("update_status", **kw)

    def remote_status(self):
        """Per il telefono (gateway /nexus/status): versione di NEXUS su questo PC e aggiornamenti attorno."""
        from . import __version__
        from .osys import os_name
        if not self.deps_state["items"] and not self.deps_state["checking"]:
            threading.Thread(target=self.deps_check, daemon=True).start()
        up = getattr(self, "update_state", {}) or {}
        return {"nexus": {"version": __version__, "current": up.get("current", ""), "behind": up.get("behind", 0),
                          "news": up.get("news", [])[:4], "packaged": bool(IS_WIN or PACKAGED)},
                "os": os_name(), "deps": self.deps_state}

    # ---------- aggiornamenti delle dipendenze (Ollama, modelli, programmi del sistema) ----------
    def _deps_emit(self, **kw):
        self.deps_state.update(kw)
        self.bus.emit("deps_status", **self.deps_state)

    def deps_check(self):
        from . import deps
        with self.deps_lock:
            busy = self.deps_state["checking"] or self.deps_state["working"]
            if not busy:
                self.deps_state["checking"] = True
        if busy:
            return self.bus.emit("deps_status", **self.deps_state)
        self._deps_emit(checking=True, error="")
        try:
            self._deps_emit(items=deps.check(self.cfg), checking=False)
        except Exception as e:
            self._deps_emit(checking=False, error=str(e)[:160])

    def deps_apply(self, item_id):
        from . import deps
        st = self.deps_state
        item = next((i for i in st["items"] if i["id"] == item_id), None)
        with self.deps_lock:
            if not item or not item.get("action") or st["working"] or st["checking"]:
                return
            st["working"] = item_id
        self._deps_emit(working=item_id, text="", pct=-1, error="")
        try:
            msg = deps.apply(self.cfg, item["action"], lambda t, pct=-1: self._deps_emit(text=t, pct=pct), item)
            self._deps_emit(working="", text=msg, pct=-1)
        except Exception as e:
            self._deps_emit(working="", text="", error=str(e)[:200])
            return
        if item["action"] != "system":               # il terminale lo chiude l'utente: lì ricontrolla lui
            self.deps_check()

    def _git(self, *args, timeout=60):
        from .config import ROOT
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout)

    def update_check(self):
        if IS_WIN or PACKAGED:
            return self._win_update_check()
        try:
            cur = self._git("log", "-1", "--format=%h · %cd", "--date=format:%d/%m/%Y %H:%M").stdout.strip()
            f = self._git("fetch", "-q", "origin")
            if f.returncode != 0:
                raise RuntimeError(f.stderr.strip()[:120] or "git fetch non riuscito")
            behind = int(self._git("rev-list", "--count", "HEAD..@{u}").stdout.strip() or 0)
            news = self._git("log", "--format=• %s", "HEAD..@{u}").stdout.strip().splitlines()[:6]
            self._update_emit(current=cur, behind=behind, news=news, error="")
        except Exception as e:
            self._update_emit(current="", behind=0, news=[], error=str(e)[:160])

    def update_apply(self):
        if IS_WIN or PACKAGED:
            return self._win_update_apply()
        from .config import ROOT
        self._update_emit(current="", behind=0, news=[], error="", working=True)
        old_req = (ROOT / "backend/requirements.txt").read_text()
        r = self._git("pull", "--ff-only", timeout=180)
        if r.returncode != 0:
            self._update_emit(current="", behind=0, news=[], error="git pull: " + (r.stderr or r.stdout)[-160:])
            return
        if (ROOT / "backend/requirements.txt").read_text() != old_req:
            subprocess.run(["uv", "pip", "install", "-p", str(ROOT / "backend/.venv/bin/python"), "-r",
                            str(ROOT / "backend/requirements.txt")], capture_output=True, timeout=1200)
        self._update_emit(current="", behind=0, news=[], error="", restarting=True)
        # riavvio: systemd se c'è, altrimenti rilancia lo script
        subprocess.Popen(["sh", "-c", "sleep 1; systemctl --user --no-block restart nexus-backend nexus-ui || "
                          f"(pkill -f 'nexus.main'; pkill -f 'ui/app.py'; setsid {ROOT}/scripts/nexus >/dev/null 2>&1 &)"],
                         start_new_session=True)

    def log_chat(self, text, reply, seconds, task=None):
        """Registro locale delle conversazioni (~/.local/share/nexus/chats.jsonl), utile per capire cosa migliorare."""
        from .config import DATA
        rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "user": text, "reply": reply,
               "seconds": round(seconds, 1), "model": self.cfg.active_provider().get("model"),
               "steps": getattr(task, "log_steps", [])}
        try:
            with open(DATA / "chats.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------- provider ----------
    # ---------- Playwright MCP: il browser vero ----------
    def _bmcp_status(self, **k):
        self.bmcp_status = {"state": k.get("state", ""), "browser": k.get("browser", ""), "text": k.get("text", "")}
        self.bus.emit("browser_mcp", **self.bmcp_status)

    def browser_start(self):
        from .browsermcp import BrowserMCP, register
        from .tools import REGISTRY
        self.browser_stop(quiet=True)
        try:
            self.bmcp = BrowserMCP(self.cfg, status=self._bmcp_status)
            if self.bmcp.start():
                register(self.bmcp, REGISTRY)
        except Exception as e:
            print("Playwright MCP:", e)
            self._bmcp_status(state="error", browser="", text=f"Playwright non partito: {str(e)[:140]}")

    def browser_stop(self, quiet=False):
        from .browsermcp import unregister
        from .tools import REGISTRY
        unregister(REGISTRY)
        if self.bmcp:
            self.bmcp.stop()
            self.bmcp = None
        elif not quiet:
            self._bmcp_status(state="off", browser="", text="Spento")

    # ---------- la tua voce come parola di attivazione ----------
    def wake_record(self):
        """Registra "Ehi <nome>" tre volte: poi NEXUS ti riconosce dal suono della voce."""
        if not self.ears or self.ears.stream is None:
            self.bus.emit("wake_voice", ready=False, step=0, text="Non trovo il microfono.")
            return
        name = self.cfg.get("agent_name") or "Nexus"
        if not self.mic.acquire(timeout=10):
            self.bus.emit("wake_voice", ready=False, step=0, text="Sto già ascoltando: riprova tra poco.")
            return
        try:
            clips = self._wake_clips(name)
        finally:
            self.mic.release()
        self._wake_save(name, clips)

    def _wake_clips(self, name):
        clips = []
        tries = 0
        while len(clips) < 3 and tries < 6:
            tries += 1
            self.bus.emit("wake_voice", ready=False, step=len(clips) + 1,
                          text=f"Di' “Ehi {name}” ({len(clips) + 1} di 3)…")
            self.set_state("listening", f"Di' “Ehi {name}”")
            self.voice.beep("wake")
            a = self.ears.record(wait=4.0, silence=0.5, max_s=4.0)
            if a is None or not 0.35 <= len(a) / 16000 <= 4.0:
                self.bus.emit("wake_voice", ready=False, step=len(clips) + 1, text="Non ti ho sentito, riprova.")
                time.sleep(1.0)
                continue
            clips.append(a)
            time.sleep(0.5)
        self.set_state("idle", self._idle_text())
        return clips

    def _wake_save(self, name, clips):
        from .wakevoice import VoiceMatcher
        if len(clips) < 3:
            self.bus.emit("wake_voice", ready=False, step=0, text="Registrazione non completata: riprova.")
            return
        sp = self.ears.spotter
        vm = sp.voice if sp is not None and sp.voice is not None else VoiceMatcher()
        vm.save(clips)
        if sp is not None:
            sp.voice = vm
        self.bus.emit("wake_voice", ready=True, step=0, text=f"Fatto: ora ti riconosco quando dici “Ehi {name}”.")

    # ---------- chat salvate ----------
    def _lane(self, desk=None):
        """Memoria breve del cervello per un desktop virtuale (0 = desktop unico / non si sa)."""
        if desk is None:
            desk = desktops.current()
        return self.lanes.setdefault(desk or 0, {"history": [], "last": 0.0})

    def _current_chat(self):
        """La chat in corso; dopo una pausa più lunga della memoria del cervello ne comincia una nuova."""
        from . import chats
        if self.chat is None or time.time() - self.chat["updated"] > self.cfg["memory_minutes"] * 60:
            self.chat = chats.new()
        return self.chat

    def _chat_add(self, role, text, task=None):
        from . import chats
        with self.chat_lock:                       # più compiti possono scrivere insieme
            c = self._current_chat()
            chats.add(c, role, text)
            if role == "assistant":
                c["history"] = list(self._lane(task.desktop if task else None)["history"])
                chats.save(c)
        self.bus.emit("chat_message", id=c["id"], title=c["title"], role=role, text=text)

    def _emit_chat(self):
        c = self.chat or {"id": "", "title": "", "messages": []}
        self.bus.emit("chat", id=c["id"], title=c.get("title", ""), messages=c["messages"])

    def chat_command(self, t, msg):
        from . import chats
        cid = msg.get("id", "")
        if t == "chat_open":
            c = chats.load(cid)
            if c:
                c["updated"] = time.time()          # riaperta: il discorso continua da qui
                self.chat = c
                lane = self._lane()
                lane["history"] = list(c.get("history") or [])
                lane["last"] = time.time()
            self._emit_chat()
            return
        if t == "chat_new":
            self.chat = None
            self._lane()["history"] = []
            self._emit_chat()
        elif t == "chat_delete":
            chats.delete(cid)
            if self.chat and self.chat["id"] == cid:
                self.chat = None
                self._lane()["history"] = []
                self._emit_chat()
        elif t == "chat_rename":
            chats.rename(cid, msg.get("title", ""))
            if self.chat and self.chat["id"] == cid:
                self.chat = chats.load(cid)
                self._emit_chat()
        self.bus.emit("chats", list=chats.listing(msg.get("query", "")), query=msg.get("query", ""),
                      current=self.chat["id"] if self.chat else "")

    # ---------- modelli di Ollama (Personalizza → Modelli) ----------
    def models_command(self, t, msg):
        from . import models
        p = models.target(self.cfg)
        name = (msg.get("name") or "").strip()

        def progress(text, pct=-1, done=False, error=""):
            self.bus.emit("model_progress", name=name, text=text, pct=pct, done=done, error=error)
        try:
            if p is None:
                raise RuntimeError("aggiungi prima un cervello Ollama (questo PC o un PC in rete)")
            if t == "models_search":
                from .winsetup import vram_mb
                v = vram_mb()
                rs = models.search(msg.get("query", ""))
                for r in rs:
                    for s in r["sizes"]:
                        s["fit"] = models.fits(s["gb"], v)
                self.bus.emit("models_search", results=rs, vram_gb=round(v / 1024, 1))
                return
            if t == "model_pull":
                progress(f"Scarico {name}…", 0)
                models.pull(p, name, progress)
                if msg.get("use"):
                    p["model"] = name
                    self.cfg["provider"] = p["id"]
                    self.cfg.save()
                    self.bus.emit("config", config=self.cfg.public())
                progress(f"{name} installato" + (" e in uso" if msg.get("use") else ""), 100, done=True)
            elif t == "model_delete":
                models.delete(p, name)
            elif t == "model_use":
                p["model"] = name
                self.cfg["provider"] = p["id"]
                self.cfg.save()
                self.bus.emit("config", config=self.cfg.public())
            self.bus.emit("models", target=p.get("name", ""), url=p.get("base_url", ""),
                          current=p.get("model", ""), installed=models.installed(p), error="")
        except Exception as e:
            if t == "model_pull":
                err = str(e)[:200]
                if "requires ollama version" in err or "newer version of ollama" in err.lower():
                    err += " · Aggiorna Ollama da Personalizza → Aggiornamenti"
                    threading.Thread(target=self.deps_check, daemon=True).start()
                progress("", error=err)
            else:
                self.bus.emit("models", target=(p or {}).get("name", ""), url=(p or {}).get("base_url", ""),
                              current=(p or {}).get("model", ""), installed=[], error=str(e)[:200])

    def provider_command(self, t, msg):
        from .providers import make, PRESETS
        cfg = self.cfg
        if t == "provider_save":
            p = dict(msg.get("provider", {}))
            old = cfg.get_provider(p.get("id")) if p.get("id") else None
            if not p.get("api_key") and old:             # chiave vuota = tieni quella salvata
                p["api_key"] = old.get("api_key", "")
            p.setdefault("kind", PRESETS.get(p.get("preset"), {}).get("kind", "openai"))
            p.pop("api_key_hint", None)
            if old:
                old.update(p)
            else:
                p["id"] = p.get("id") or uuid.uuid4().hex[:8]
                cfg["providers"].append(p)
            if msg.get("select"):
                cfg["provider"] = p["id"]
            cfg.save()
            self.bus.emit("config", config=cfg.public())
            self.bus.emit("provider_result", ok=True, text=f"Salvato: {p.get('name')}")
        elif t == "provider_delete":
            pid = msg.get("id")
            if len(cfg["providers"]) > 1:
                cfg["providers"] = [p for p in cfg["providers"] if p["id"] != pid]
                if cfg["provider"] == pid:
                    cfg["provider"] = cfg["providers"][0]["id"]
                cfg.save()
            self.bus.emit("config", config=cfg.public())
        else:
            # provider da provare: quello salvato (per id) con eventuali modifiche non ancora salvate
            p = dict(cfg.get_provider(msg.get("id")) or {})
            draft = msg.get("provider") or {}
            p.update({k: v for k, v in draft.items() if v not in ("", None) and k != "api_key_hint"})
            p.setdefault("kind", PRESETS.get(p.get("preset"), {}).get("kind", "openai"))
            try:
                # alcuni servizi (Gemini) li chiamano "models/gemini-2.5-flash": per chiederli basta il nome
                models = sorted({m.removeprefix("models/") for m in make(p, cfg).list_models()})
                if t == "provider_models":
                    self.bus.emit("provider_models", id=msg.get("id"), models=models[:500])
                else:
                    want = (p.get("model") or "").removeprefix("models/")
                    if not want or want in models or not models:
                        self.bus.emit("provider_result", ok=True, text=f"Connesso: {len(models)} modelli disponibili"
                                      + (f", “{want}” c'è" if want else ""))
                    else:
                        import difflib
                        near = difflib.get_close_matches(want, models, n=1, cutoff=0.3)
                        self.bus.emit("provider_models", id=msg.get("id"), models=models[:500])
                        self.bus.emit("provider_result", ok=False, text=f"Connesso, ma il modello “{want}” non c'è con questa chiave: "
                                      + (f"forse “{near[0]}”? " if near else "") + "scegline uno dall'elenco qui sopra.")
            except Exception as e:
                self.bus.emit("provider_result", ok=False, text=f"Connessione fallita: {str(e)[:160]}")

    # ---------- compiti: "Ehi Nexus" anche mentre lavora, "Ehi Nexus basta" per fermare ----------
    def on_wake(self, text=None, audio=None, during=False):
        """Parola di attivazione sentita. `during` = mentre NEXUS parlava: smette subito di parlare."""
        if during or self.speech.locked():
            self.voice.stop()
        name = self.cfg.get("agent_name") or "Nexus"
        rest = (text or "").strip()
        if rest and rest != "…" and T.is_stop(rest, name):
            return self.stop_command(rest)
        if rest != "…" and len(rest) <= 2:
            return self._spawn(None)
        if audio is None or self.stt is None:
            return self._spawn(None if rest == "…" else rest)

        def precise():
            # il riconoscimento del nome sbaglia il resto: la domanda la ritrascrive quello principale
            from .wakename import match, match_anywhere
            q = None if rest == "…" else rest
            try:
                full = self.stt.transcribe(audio)
                ok, r = (match_anywhere if during else match)(full, name)
                if ok and len(r) > 2:
                    q = r
                elif q is None and not during:
                    # svegliato dalla voce: il nome è all'inizio ma trascritto storto ("Eto bot accendi la luce")
                    w = full.split()
                    q = " ".join(w[2:]) if len(w) > 3 else None
            except Exception as e:
                print("trascrizione della domanda:", e)
            if q and T.is_stop(q, name):
                return self.stop_command(q)
            self._spawn(q)
        threading.Thread(target=precise, daemon=True).start()

    def _attachments(self, files):
        """File e immagini incollati (Ctrl+V) o trascinati nella chat: (note per il cervello, immagini)."""
        from pathlib import Path
        from .config import CACHE
        notes, images = [], []
        for f in files[:6]:
            p = Path(str(f).removeprefix("file://")).expanduser()
            if not p.is_file():
                continue
            if p.suffix.lower() in IMG_EXT:
                try:
                    from PIL import Image
                    img = Image.open(p).convert("RGB")
                    img.thumbnail((1600, 1600))
                    out = CACHE / f"allegato_{uuid.uuid4().hex[:8]}.jpg"
                    img.save(out, quality=88)
                    images.append(str(out))
                    notes.append(f"[immagine allegata: {p.name}]")
                except Exception as e:
                    notes.append(f"[immagine {p.name} non leggibile: {e}]")
                continue
            txt = None
            if p.stat().st_size <= 60_000:
                try:
                    txt = p.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    txt = None
            if txt is not None:
                notes.append(f"[file allegato {p}, contenuto:]\n{txt[:12000]}")
            else:
                notes.append(f"[file allegato: {p} ({p.stat().st_size // 1024} KB): usa i tool sui file se serve]")
        return notes, images

    def _spawn(self, text, files=None):
        """Nuovo compito, anche se un altro sta già lavorando (in parallelo)."""
        if self.brain is None:
            return
        name = self.cfg.get("agent_name") or "Nexus"
        if text and not files and T.is_stop(text, name):
            return self.stop_command(text)
        notes, images = self._attachments(files) if files else ([], [])
        with self.tasks_lock:
            live = [t for t in self.tasks.values() if not t.cancelled]
            if text is None and (self.mic.locked() or any(t.listening for t in live)):
                return                                 # sta già ascoltando
            if len(live) >= T.MAX_TASKS:
                threading.Thread(target=self.say, args=(None, "Sto già facendo quattro cose: aspetta che ne finisca "
                                 "una, oppure dimmi basta."), daemon=True).start()
                return
            shown = text
            if files:
                names = ", ".join(os.path.basename(str(f)) for f in files[:6])
                shown = ((text or "") + f"\n📎 {names}").strip()
            task = T.Task(shown, desktops.current(), images)
            task.prompt = ((text or "Guarda l'allegato.") + "\n\n" + "\n".join(notes)) if files else None
            task.ctx = Ctx(self, task)
            first = not self.tasks
            self.tasks[task.id] = task
        if first:
            self.bus.emit("session", start=True)
        self._emit_tasks()
        threading.Thread(target=self.session, args=(task,), daemon=True, name="task-" + task.id).start()

    def _live(self):
        with self.tasks_lock:
            return [t for t in self.tasks.values() if not t.cancelled]

    def _emit_tasks(self):
        self.bus.emit("tasks", list=[t.info() for t in self._live()], current=desktops.current())

    def task_step(self, task, icon, text):
        """Passo di un compito nel notch; con più compiti insieme (o da un altro desktop) dice di quale desktop è."""
        task.step = text
        many = len(self._live()) > 1
        tag = f"D{task.desktop} · " if task.desktop and (many or not desktops.is_current(task.desktop)) else ""
        self.bus.emit("step", icon=icon, text=tag + text)
        self._emit_tasks()

    def _others(self, task):
        """Per il cervello: gli altri compiti in corso (così sa rispondere a "a che punto sei?")."""
        live = [t for t in self._live() if t is not task and t.text]
        if not live:
            return ""
        lines = [f"- «{t.text[:120]}»" + (f" (desktop {t.desktop})" if t.desktop else "")
                 + (f", adesso: {t.step}" if t.step else "") for t in live]
        return ("\n\nALTRI COMPITI IN CORSO (li sta facendo in parallelo un'altra parte di te: non rifarli e non "
                "fermarli; se l'utente chiede a che punto sono, rispondi con queste informazioni):\n" + "\n".join(lines))

    def before_tool(self, task, name, args):
        """Prima di ogni tool di un compito: le mani (schermo/mouse/browser) le usa un compito alla volta e
        schermo/mouse solo sul desktop del compito. Le finestre che apre vanno sul desktop del compito.
        Ritorna una nota per il cervello; "SKIP:…" = non eseguire (lo schermo è cambiato mentre aspettava)."""
        from .tools import REGISTRY
        waited = []
        if T.needs_hands(name, REGISTRY):
            def on_wait(kind, other):
                waited.append(kind)
                if kind == "desktop":
                    self.task_step(task, "⏸", f"Mi servono schermo e mouse: torna sul desktop {task.desktop}")
                    self.say(None, f"Per continuare il compito del desktop {task.desktop}, torna su quel desktop.")
                else:
                    what = f"«{other.text[:50]}»" if other is not None and other.text else "l'altro compito"
                    self.task_step(task, "⏳", f"Aspetto che finisca {what}")
            self.hands.acquire(task, name in T.SCREEN, on_wait)
            if waited:
                self.task_step(task, "▶", "Riprendo")
                if name in BLIND:
                    return ("SKIP:Non l'ho fatto: hai aspettato un altro compito o il cambio di desktop e lo schermo "
                            "può essere cambiato. Guarda di nuovo lo schermo (look_screen) e poi rifai l'azione.")
        if name in T.OPENERS and task.desktop:
            try:
                desktops.follow(task.desktop, T.window_hints(name, args, self.cfg))
            except Exception as e:
                print("finestre sul desktop del compito:", e)
        return ""

    def _settle(self):
        """Stato del notch quando una parte finisce: ascolta/parla hanno la precedenza, poi i compiti, poi riposo."""
        if self.speech.locked() or self.mic.locked():
            return
        live = self._live()
        if live:
            detail = f"{len(live)} compiti in corso" if len(live) > 1 else (live[-1].step or "Penso…")
            self.set_state("thinking", detail)
        else:
            self.set_state("idle", self._idle_text())

    def _busy_state(self, state, detail):
        """Stato di un compito, ma senza coprire "ti ascolto" o "sto parlando" di un altro."""
        if not self.speech.locked() and not self.mic.locked():
            self.set_state(state, detail)

    def say(self, task, text):
        """Parla (una risposta alla volta: le altre aspettano in coda). Un compito fermato non parla più."""
        if not text or self.voice is None:
            return
        with self.speech:
            if task is not None and task.cancelled:
                return
            self.voice.reset()
            self.speaking_task = task
            self.set_state("speaking", "")
            try:
                self.voice.speak(text)
            finally:
                self.speaking_task = None
        self._settle()

    def listen_once(self, task=None, wait=5.0, beep=False, block=True):
        if self.ears.stream is None:
            self.bus.emit("log", text="Nessun microfono: scrivimi la richiesta.")
            return ""
        if not self.mic.acquire(timeout=10 if block else 0.01):
            return ""                                   # sta ascoltando un altro compito
        try:
            if task is not None:
                if task.cancelled:
                    return ""
                task.listening = True
            if beep:
                self.voice.beep("wake")
            self.set_state("listening", "Ti ascolto…")
            audio = self.ears.record(wait=wait)
        finally:
            if task is not None:
                task.listening = False
            self.mic.release()
        if audio is None:
            self._settle()
            return ""
        self._busy_state("thinking", "Trascrivo…")
        return self.stt.transcribe(audio)

    def session(self, task):
        from .brain import Cancelled
        lane = self._lane(task.desktop)
        text = task.text or None
        prompt = getattr(task, "prompt", None)
        try:
            for turn in range(4):
                if task.cancelled:
                    break
                if text is None:
                    text = self.listen_once(task, wait=5.0 if turn == 0 else 4.0, beep=turn == 0, block=turn == 0)
                    if not text or task.cancelled:
                        break
                    if T.is_stop(text, self.cfg.get("agent_name") or ""):
                        self.stop_command(text, skip=task)     # "Ehi Nexus" … "basta"
                        break
                    task.text = text
                    self._emit_tasks()
                self.bus.emit("transcript", text=text)
                self._chat_add("user", text, task)
                quick = self.quick_command(text)
                if quick:                              # comandi istantanei, senza passare dal cervello
                    self._chat_add("assistant", quick, task)
                    self.bus.emit("reply", text=quick)
                    self.say(task, quick)
                    break
                self._busy_state("thinking", "Penso…")
                t0 = time.time()
                reply = self.brain.run(prompt or text, task, lane,
                                       images=task.attachments if turn == 0 else None, others=self._others(task))
                prompt = None
                self.log_chat(text, reply, time.time() - t0, task)
                self._chat_add("assistant", reply, task)
                if task.cancelled:
                    break
                self.bus.emit("reply", text=reply)
                self.say(task, reply)
                if task.cancelled or not reply.rstrip().endswith("?"):
                    break
                text = None  # domanda → ascolta la risposta senza wake word
        except Cancelled:
            pass
        except Exception as e:
            traceback.print_exc()
            self.bus.emit("reply", text=f"Errore: {e}")
            self.set_state("error", str(e)[:120])
            try:
                self.voice.beep("error")
            except Exception:
                pass
        finally:
            self.hands.release(task)
            with self.tasks_lock:
                self.tasks.pop(task.id, None)
                empty = not self.tasks
            self._emit_tasks()
            if empty:
                self.bus.emit("session", start=False)
            self._settle()

    def confirm(self, question, task=None):
        if self.cfg.get("auto_mode"):                       # automode: niente domande
            self.bus.emit("step", icon="⚡", text="Automode: procedo")
            return True
        with self.confirm_lock:                             # una domanda alla volta, anche con più compiti
            if task is not None and task.cancelled:
                return False
            cid = uuid.uuid4().hex[:8]
            p = {"ev": threading.Event(), "ok": False, "task": task}
            self.pending[cid] = p
            self.bus.emit("confirm", id=cid, text=question)
            self.say(task, question + " Di' sì o no.")

            def by_voice():
                while not p["ev"].is_set() and not (task is not None and task.cancelled):
                    ans = self.listen_once(task, wait=8.0, block=False)
                    if p["ev"].is_set():
                        return
                    if ans and NO.search(ans):
                        p["ok"] = False; p["ev"].set()
                    elif ans and YES.search(ans):
                        p["ok"] = True; p["ev"].set()
                    elif not ans:
                        return  # silenzio (o microfono occupato): aspetta il click
            listener = threading.Thread(target=by_voice, daemon=True)
            listener.start()
            end = time.time() + 30
            while not p["ev"].wait(0.3) and time.time() < end:
                if task is not None and task.cancelled:
                    break
            p["ev"].set()
            if task is not None and task.listening:
                self.ears.cancel()
            listener.join(3)
            self.pending.pop(cid, None)
            self.bus.emit("confirm", id=None, text="")
            self._busy_state("acting", "Procedo…" if p["ok"] else "Annullato")
            return p["ok"] and not (task is not None and task.cancelled)


def main():
    Nexus().start()


if __name__ == "__main__":
    main()
