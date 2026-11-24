"""Microfono sempre acceso: parola di attivazione + registrazione del comando."""
import collections
import queue
import threading
import time

import numpy as np
import sounddevice as sd

RATE = 16000
CHUNK = 1280  # 80 ms, quello che vuole openWakeWord


class Ears:
    def __init__(self, cfg, bus, on_wake):
        self.cfg, self.bus, self.on_wake = cfg, bus, on_wake
        self.q = queue.Queue(maxsize=200)
        self.muted = False            # true mentre NEXUS parla
        self.noise = 200.0            # rumore di fondo stimato
        self._rec = None              # dict quando sta registrando
        self.preroll = collections.deque(maxlen=10)   # ~0,8 s di audio prima dell'inizio: non perde le prime parole
        self._cool = 0.0
        self.oww = None
        self.vad = None
        self.spotter = None            # wake_word "name": il nome scelto dall'utente (vedi wakename.py)
        self._seg = None               # frase in corso (modalità nome)
        self.load_wakeword()

    # ---------- wake word ----------
    def load_wakeword(self):
        if self.cfg["wake_word"] == "name":
            self.oww = None
            try:
                from openwakeword.utils import download_models
                try:
                    download_models([])                # modelli di base, compreso il VAD Silero
                except Exception:
                    pass
                from openwakeword.vad import VAD
                self.vad = self.vad or VAD()
            except Exception as e:
                print("VAD non disponibile:", e)
            from .wakename import NameSpotter
            self.spotter = self.spotter or NameSpotter(self.cfg)
            threading.Thread(target=self.spotter.load, daemon=True).start()     # scarica whisper tiny la prima volta
            print("parola di attivazione: il nome", self.cfg.get("agent_name"))
            return
        self.spotter = None
        try:
            from openwakeword.model import Model
            from openwakeword.utils import download_models
            try:
                download_models([self.cfg["wake_word"]])
            except Exception:
                pass
            self.oww = Model(wakeword_models=[self.cfg["wake_word"]], inference_framework="onnx")
            print("wake word pronta:", self.cfg["wake_word"])
            from openwakeword.vad import VAD
            self.vad = VAD()
        except Exception as e:
            self.oww = None
            print("wake word non disponibile:", e)
            self.bus.emit("log", text=f"Wake word non disponibile: {e}")

    # ---------- stream ----------
    def start(self):
        """Apre il microfono. Se non c'è (PC senza microfono, cuffie staccate) NEXUS parte lo stesso
        e riprova ogni 10 s: si usa scrivendo, e la voce torna appena il microfono c'è."""
        self.stream = None
        threading.Thread(target=self._loop, daemon=True, name="ears").start()
        if not self._open():
            print("nessun microfono: NEXUS parte lo stesso, riprovo ogni 10 s")
            self.bus.emit("log", text="Nessun microfono trovato: puoi scrivere, la voce torna appena colleghi un microfono.")
            threading.Thread(target=self._retry, daemon=True, name="ears-retry").start()

    def _open(self):
        def cb(indata, frames, t, status):
            try:
                self.q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass
        try:
            st = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK, callback=cb)
            st.start()
        except Exception as e:                     # PortAudioError, nessun dispositivo, driver
            self._mic_err = str(e)
            return False
        self.stream = st
        return True

    def _retry(self):
        while self.stream is None:
            time.sleep(10)
            try:
                sd._terminate(); sd._initialize()   # rilegge l'elenco dei dispositivi
            except Exception:
                pass
            if self._open():
                print("microfono trovato")
                self.bus.emit("log", text="Microfono collegato: puoi parlare.")

    def _loop(self):
        last_level = 0.0
        while True:
            chunk = self.q.get()
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            rec = self._rec
            if rec is not None:
                self._feed_record(rec, chunk, rms)
                now = time.time()
                if now - last_level > 0.05:
                    self.bus.emit("level", v=min(1.0, rms / 3000))
                    last_level = now
                continue
            self.preroll.append(chunk)
            # rumore di fondo (media lenta)
            self.noise = 0.98 * self.noise + 0.02 * min(rms, 20000)
            if self.spotter is not None:
                if not self.muted and self.cfg["wake_enabled"]:
                    self._spot_name(chunk, rms)
                else:
                    self._seg = None
                continue
            if self.oww is None or self.muted or not self.cfg["wake_enabled"]:
                continue
            scores = self.oww.predict(chunk)
            if scores and max(scores.values()) >= self.cfg["wake_threshold"] and time.time() > self._cool:
                self._cool = time.time() + 2.0
                self.oww.reset()
                self.preroll.clear()          # niente "Hey Jarvis" nella frase
                self.on_wake()

    # ---------- parola di attivazione = nome ----------
    def _spot_name(self, chunk, rms):
        """Raccoglie le frasi (VAD) e manda quelle brevi a Whisper tiny per cercare il nome.
        I tempi si contano in pezzi audio da 80 ms (CHUNK), non con l'orologio."""
        p = self.vad.predict(chunk, frame_size=640) if self.vad is not None else (1.0 if rms > 500 else 0.0)
        voice = p > 0.5 and rms > max(self.noise * 1.5, 250)
        seg = self._seg
        if voice:
            if seg is None:
                seg = self._seg = {"buf": list(self.preroll)[-3:], "n": 0, "quiet": 0}
            seg["quiet"] = 0
        elif seg is not None:
            seg["quiet"] += 1
        if seg is None:
            return
        seg["buf"].append(chunk)
        seg["n"] += 1
        step = CHUNK / RATE
        if seg["quiet"] * step > 0.45 or seg["n"] * step > 6.0:
            self._seg = None
            dur = (seg["n"] - seg["quiet"]) * step
            if 0.3 <= dur <= 6.5 and time.time() > self._cool:
                self.spotter.check(np.concatenate(seg["buf"]), self._name_hit)

    def _name_hit(self, rest, audio=None):
        if self.muted or time.time() < self._cool:
            return
        self._cool = time.time() + 2.0
        self.preroll.clear()
        try:
            self.on_wake(rest, audio)     # "Marco, che ore sono?" → la domanda va subito al cervello
        except TypeError:
            self.on_wake()

    # ---------- registrazione comando ----------
    def _feed_record(self, rec, chunk, rms):
        """Fine frase: voce = Silero sicuro (>0.6) E più forte del rumore della stanza.
        Chiude dopo `silence` secondi senza voce, al massimo dopo `max` secondi."""
        rec["buf"].append(chunk)
        now = time.time()
        p = self.vad.predict(chunk, frame_size=640) if self.vad is not None else (1.0 if rms > 400 else 0.0)
        loud = rms > max(self.noise * 1.8, 300)
        is_voice = (p > 0.6 and loud) or p > 0.85
        if is_voice:
            rec["voiced"] += 1
            if rec["voiced"] >= 2:              # almeno ~160 ms di voce vera
                rec["speech"] = True
            rec["last_voice"] = now
        else:
            rec["voiced"] = 0
        if (not rec["speech"] and now - rec["t0"] > rec["wait"]) or \
           (rec["speech"] and now - rec["last_voice"] > rec["silence"]) or \
           (now - rec["t0"] > rec["max"]):
            self._rec = None
            rec["done"].set()

    def cancel(self):
        """Interrompe una registrazione in corso (es. conferma data col click)."""
        rec = self._rec
        if rec is not None:
            rec["speech"] = False
            self._rec = None
            rec["done"].set()

    def record(self, wait=4.0, silence=0.7, max_s=15.0):
        """Registra finché l'utente parla. Ritorna int16 array o None se silenzio."""
        if self.stream is None:                   # niente microfono
            return None
        pre = list(self.preroll)
        if self.vad is not None:
            self.vad.reset_states()
        rec = {"buf": pre, "speech": False, "voiced": 0, "t0": time.time(), "last_voice": time.time(),
               "wait": wait, "silence": silence, "max": max_s, "done": threading.Event()}
        self._rec = rec
        rec["done"].wait(max_s + 2)
        self._rec = None
        self.bus.emit("level", v=0)
        if not rec["speech"]:
            return None
        return np.concatenate(rec["buf"])
