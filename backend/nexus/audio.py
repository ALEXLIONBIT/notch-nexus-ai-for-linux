"""Microfono sempre acceso: parola di attivazione + registrazione del comando."""
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
        self._cool = 0.0
        self.oww = None
        self.vad = None
        self.load_wakeword()

    # ---------- wake word ----------
    def load_wakeword(self):
        try:
            import openwakeword
            from openwakeword.model import Model
            try:
                openwakeword.utils.download_models([self.cfg["wake_word"]])
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
        def cb(indata, frames, t, status):
            try:
                self.q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass
        self.stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                                     blocksize=CHUNK, callback=cb)
        self.stream.start()
        threading.Thread(target=self._loop, daemon=True, name="ears").start()

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
            # rumore di fondo (media lenta)
            self.noise = 0.98 * self.noise + 0.02 * min(rms, 2000)
            if self.oww is None or self.muted or not self.cfg["wake_enabled"]:
                continue
            scores = self.oww.predict(chunk)
            if scores and max(scores.values()) >= self.cfg["wake_threshold"] and time.time() > self._cool:
                self._cool = time.time() + 2.0
                self.oww.reset()
                self.on_wake()

    # ---------- registrazione comando ----------
    def _feed_record(self, rec, chunk, rms):
        rec["buf"].append(chunk)
        now = time.time()
        if self.vad is not None:            # Silero VAD: capisce la voce, non solo il volume
            is_voice = self.vad.predict(chunk, frame_size=640) > (0.5 if not rec["speech"] else 0.35)
        else:
            is_voice = rms > max(self.noise * 2.5, 350)
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

    def record(self, wait=4.0, silence=0.8, max_s=20.0):
        """Registra finché l'utente parla. Ritorna int16 array o None se silenzio."""
        while not self.q.empty():
            self.q.get_nowait()
        if self.vad is not None:
            self.vad.reset_states()
        rec = {"buf": [], "speech": False, "voiced": 0, "t0": time.time(), "last_voice": time.time(),
               "wait": wait, "silence": silence, "max": max_s, "done": threading.Event()}
        self._rec = rec
        rec["done"].wait(max_s + 2)
        self._rec = None
        self.bus.emit("level", v=0)
        if not rec["speech"]:
            return None
        return np.concatenate(rec["buf"])
