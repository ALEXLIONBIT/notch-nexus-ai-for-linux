"""NEXUS backend: orecchie → cervello → mani → voce, e parla con la UI."""
import re
import threading
import traceback
import uuid

from .config import Config
from .bus import Bus

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
        self.set_state("idle", self._idle_text())
        print("NEXUS pronto.")
        threading.Event().wait()

    def _idle_text(self):
        w = self.cfg["wake_word"].replace("_", " ").title()
        return f"Di' “{w}”" if self.ears and self.ears.oww else "Clicca 🎤 per parlare"

    def set_state(self, state, detail=""):
        self.state, self.detail = state, detail
        self.bus.emit("state", state=state, detail=detail)

    def on_connect(self):
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

    # ---------- provider ----------
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
                self.set_state("thinking", "Penso…")
                reply = self.brain.run(text)
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
