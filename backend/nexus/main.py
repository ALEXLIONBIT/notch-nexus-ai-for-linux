"""NEXUS backend: orecchie → cervello → mani → voce, e parla con la UI."""
import json
import re
import subprocess
import time
import threading
import traceback
import uuid

from .config import Config
from .bus import Bus
from .osys import IS_WIN, FROZEN, PACKAGED, APPIMAGE, RELEASE_PREFIX

RELEASES = "https://api.github.com/repos/ALEXLIONBIT/notch-nexus-ai-for-linux/releases"

YES = re.compile(r"\b(s[iì]|ok|okay|certo|vai|procedi|conferm|fallo|esatto|d'accordo)\b", re.I)
NO = re.compile(r"\b(no|annulla|ferma|stop|lascia|non farlo|aspetta)\b", re.I)


class Ctx:
    """Quello che i tool vedono: passi nel notch, immagini, conferme."""
    def __init__(self, nexus):
        self.n = nexus
        self.cfg = nexus.cfg

    def step(self, icon, text):
        self.n.bus.emit("step", icon=icon, text=text)

    def image(self, path):
        self.n.bus.emit("image", path=path)

    def confirm(self, question):
        return self.n.confirm(question)


class Nexus:
    def __init__(self):
        self.cfg = Config()
        self.bus = Bus(self.cfg["host"], self.cfg["port"], self.on_command, self.on_connect)
        self.busy = threading.Lock()
        self.state = "loading"
        self.pending = {}
        self.stopped = False
        self.ears = self.voice = self.stt = self.brain = None

    # ---------- avvio ----------
    def start(self):
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
        self.stt = Stt(self.cfg)
        self.brain = Brain(self.cfg, Tools(Ctx(self)), Ctx(self))
        self.ears.start()
        try:                                    # porta per telefono/tablet (cervello + immagini)
            from . import gateway
            gateway.start()
        except OSError as e:
            print("gateway non avviato:", e)
        threading.Thread(target=self.update_check, daemon=True).start()
        self.set_state("idle", self._idle_text())
        print("NEXUS pronto.")
        if not FROZEN:
            threading.Event().wait()          # nell'app Windows il backend gira in un thread e la UI tiene vivo il processo

    def _idle_text(self):
        w = self.cfg["wake_word"].replace("_", " ").title()
        if self.ears and self.ears.stream is None:
            return "Nessun microfono: scrivimi"
        return f"Di' “{w}”" if self.ears and self.ears.oww else "Clicca 🎤 per parlare"

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

    # ---------- comandi dalla UI ----------
    def on_command(self, msg):
        t = msg.get("type")
        if t == "listen":
            self.on_wake()
        elif t == "text" and msg.get("text", "").strip():
            self._spawn(msg["text"].strip())
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
        elif t in ("models_installed", "models_search", "model_pull", "model_delete", "model_use"):
            threading.Thread(target=self.models_command, args=(t, msg), daemon=True).start()
        elif t in ("provider_save", "provider_delete", "provider_models", "provider_test"):
            threading.Thread(target=self.provider_command, args=(t, msg), daemon=True).start()

    def stop(self):
        """Ferma TUTTO subito: voce, ascolto, ragionamento, conferme."""
        self.stopped = True
        if self.voice:
            self.voice.stop()
        if self.brain:
            self.brain.cancelled = True
        if self.ears:
            self.ears.cancel()
        for p in list(self.pending.values()):
            p["ok"] = False
            p["ev"].set()
        self.bus.emit("say", text="", dur=0, first=True, last=True)
        if self.busy.locked():
            self.set_state("idle", "Fermato")

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
            self.bus.emit("update_status", current=__version__, behind=1 if newer else 0,
                          news=[f"Versione {latest}"] + ["• " + n for n in news] if newer else [], error="")
        except Exception as e:
            self.bus.emit("update_status", current=__version__, behind=0, news=[], error=str(e)[:160])

    def _win_update_apply(self):
        """Scarica l'installer nuovo, lo avvia in silenzio e chiude NEXUS (l'installer lo riapre)."""
        import os
        import urllib.request
        from .config import CACHE
        self.bus.emit("update_status", current="", behind=0, news=[], error="", working=True)
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
            self.bus.emit("update_status", current="", behind=0, news=[], error="download: " + str(e)[:150])
            return
        self.bus.emit("update_status", current="", behind=0, news=[], error="", restarting=True)
        if not IS_WIN:
            # AppImage: sostituisce il file con quello nuovo e lo riapre
            import shutil
            target = APPIMAGE or str(dest)
            os.chmod(dest, 0o755)
            if APPIMAGE:
                shutil.move(str(dest), APPIMAGE + ".new")
                os.replace(APPIMAGE + ".new", APPIMAGE)
            subprocess.Popen(["sh", "-c", f'sleep 2; exec "{target}"'], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            os._exit(0)
        subprocess.Popen(f'cmd /c timeout /t 2 /nobreak >nul & "{dest}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
                         creationflags=0x08000000, close_fds=True)
        time.sleep(0.5)
        os._exit(0)

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
            self.bus.emit("update_status", current=cur, behind=behind, news=news, error="")
        except Exception as e:
            self.bus.emit("update_status", current="", behind=0, news=[], error=str(e)[:160])

    def update_apply(self):
        if IS_WIN or PACKAGED:
            return self._win_update_apply()
        from .config import ROOT
        self.bus.emit("update_status", current="", behind=0, news=[], error="", working=True)
        old_req = (ROOT / "backend/requirements.txt").read_text()
        r = self._git("pull", "--ff-only", timeout=180)
        if r.returncode != 0:
            self.bus.emit("update_status", current="", behind=0, news=[], error="git pull: " + (r.stderr or r.stdout)[-160:])
            return
        if (ROOT / "backend/requirements.txt").read_text() != old_req:
            subprocess.run(["uv", "pip", "install", "-p", str(ROOT / "backend/.venv/bin/python"), "-r",
                            str(ROOT / "backend/requirements.txt")], capture_output=True, timeout=1200)
        self.bus.emit("update_status", current="", behind=0, news=[], error="", restarting=True)
        # riavvio: systemd se c'è, altrimenti rilancia lo script
        subprocess.Popen(["sh", "-c", "sleep 1; systemctl --user restart nexus-backend nexus-ui || "
                          f"(pkill -f 'nexus.main'; pkill -f 'ui/app.py'; setsid {ROOT}/scripts/nexus >/dev/null 2>&1 &)"],
                         start_new_session=True)

    def log_chat(self, text, reply, seconds):
        """Registro locale delle conversazioni (~/.local/share/nexus/chats.jsonl), utile per capire cosa migliorare."""
        from .config import DATA
        rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "user": text, "reply": reply,
               "seconds": round(seconds, 1), "model": self.cfg.active_provider().get("model"),
               "steps": getattr(self.brain, "log_steps", [])}
        try:
            with open(DATA / "chats.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ---------- provider ----------
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
                progress("", error=str(e)[:200])
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
                models = make(p, cfg).list_models()
                if t == "provider_models":
                    self.bus.emit("provider_models", id=msg.get("id"), models=models[:300])
                else:
                    ok_model = not p.get("model") or p["model"] in models or not models
                    self.bus.emit("provider_result", ok=True, text=f"Connesso: {len(models)} modelli disponibili"
                                  + ("" if ok_model else f" (attenzione: '{p['model']}' non è nella lista)"))
            except Exception as e:
                self.bus.emit("provider_result", ok=False, text=f"Connessione fallita: {str(e)[:160]}")

    # ---------- sessione di conversazione ----------
    def on_wake(self):
        self._spawn(None)

    def _spawn(self, text):
        if self.brain is None or self.busy.locked():
            return
        threading.Thread(target=self.session, args=(text,), daemon=True).start()

    def listen_once(self, wait=5.0):
        if self.ears.stream is None:
            self.bus.emit("log", text="Nessun microfono: scrivimi la richiesta.")
            return ""
        self.set_state("listening", "Ti ascolto…")
        audio = self.ears.record(wait=wait)
        if audio is None:
            return ""
        self.set_state("thinking", "Trascrivo…")
        return self.stt.transcribe(audio)

    def session(self, text):
        if not self.busy.acquire(blocking=False):
            return
        self.stopped = False
        self.voice.reset()
        from .brain import Cancelled
        try:
            self.bus.emit("session", start=True)
            for turn in range(4):
                if self.stopped:
                    break
                if text is None:
                    if turn == 0:
                        self.voice.beep("wake")
                    text = self.listen_once(wait=5.0 if turn == 0 else 4.0)
                    if not text or self.stopped:
                        break
                self.bus.emit("transcript", text=text)
                quick = self.quick_command(text)
                if quick:                              # comandi istantanei, senza passare dal cervello
                    self.bus.emit("reply", text=quick); self.set_state("speaking", ""); self.voice.speak(quick)
                    break
                self.set_state("thinking", "Penso…")
                t0 = time.time()
                reply = self.brain.run(text)
                self.log_chat(text, reply, time.time() - t0)
                if self.stopped:
                    break
                self.bus.emit("reply", text=reply)
                self.set_state("speaking", "")
                self.voice.speak(reply)
                if self.stopped or not reply.rstrip().endswith("?"):
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
            self.bus.emit("session", start=False)
            self.set_state("idle", self._idle_text())
            self.busy.release()

    def confirm(self, question):
        if self.cfg.get("auto_mode"):                       # automode: niente domande
            self.bus.emit("step", icon="⚡", text="Automode: procedo")
            return True
        cid = uuid.uuid4().hex[:8]
        p = {"ev": threading.Event(), "ok": False}
        self.pending[cid] = p
        self.bus.emit("confirm", id=cid, text=question)
        if self.stopped:
            return False
        self.set_state("speaking", "")
        self.voice.speak(question + " Di' sì o no.")

        def by_voice():
            while not p["ev"].is_set() and not self.stopped:
                ans = self.listen_once(wait=8.0)
                if p["ev"].is_set():
                    return
                if ans and NO.search(ans):
                    p["ok"] = False; p["ev"].set()
                elif ans and YES.search(ans):
                    p["ok"] = True; p["ev"].set()
                elif not ans:
                    return  # silenzio: aspetta il click
        listener = threading.Thread(target=by_voice, daemon=True)
        listener.start()
        p["ev"].wait(30)
        p["ev"].set()
        self.ears.cancel()
        listener.join(3)
        self.pending.pop(cid, None)
        self.bus.emit("confirm", id=None, text="")
        self.set_state("acting", "Procedo…" if p["ok"] else "Annullato")
        return p["ok"]


def main():
    Nexus().start()


if __name__ == "__main__":
    main()
