"""Testo → voce: Piper (locale) + filtro robot + livello audio per la 'bocca'."""
import re
import threading

import numpy as np
import sounddevice as sd

from .config import VOICES_DIR


def clean_for_speech(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[*_#`>|]", "", text)
    text = re.sub(r"https?://\S+", "un link", text)
    return re.sub(r"\s+", " ", text).strip()


class Voice:
    def __init__(self, cfg, bus, ears):
        self.cfg, self.bus, self.ears = cfg, bus, ears
        self.voice = None
        self._stop = threading.Event()
        self.load()

    def load(self):
        try:
            from piper import PiperVoice
            path = VOICES_DIR / f"{self.cfg['voice']}.onnx"
            self.voice = PiperVoice.load(str(path))
            print("voce pronta:", path.name)
        except Exception as e:
            self.voice = None
            print("voce non disponibile:", e)
            self.bus.emit("log", text=f"Voce non disponibile: {e}")

    # ---------- sintesi ----------
    def _synth(self, text):
        speed = max(0.5, min(2.0, float(self.cfg["voice_speed"])))
        v = self.voice
        try:  # piper-tts >= 1.3
            from piper import SynthesisConfig
            chunks = list(v.synthesize(text, syn_config=SynthesisConfig(length_scale=1.0 / speed)))
            rate = chunks[0].sample_rate
            audio = np.concatenate([c.audio_int16_array for c in chunks])
        except ImportError:  # piper-tts 1.2
            raw = b"".join(v.synthesize_stream_raw(text, length_scale=1.0 / speed))
            rate = v.config.sample_rate
            audio = np.frombuffer(raw, dtype=np.int16)
        return audio.astype(np.float32) / 32768.0, rate

    def _robotize(self, x, rate):
        s = float(self.cfg["robot_strength"])
        if s <= 0:
            return x
        t = np.arange(len(x)) / rate
        ring = x * np.sin(2 * np.pi * 55 * t)                 # modulazione ad anello
        y = (1 - 0.6 * s) * x + 0.6 * s * ring
        d = int(rate * 0.007)                                   # eco metallica corta
        out = y.copy()
        out[d:] += 0.45 * s * y[:-d]
        out /= max(1e-6, np.max(np.abs(out))) / 0.9
        return out.astype(np.float32)

    # ---------- riproduzione ----------
    def speak(self, text):
        """Parla frase per frase e manda i sottotitoli alla UI in sincrono."""
        text = clean_for_speech(text)
        if not text or self.voice is None:
            return
        sentences = [x for x in re.split(r"(?<=[.!?;:])\s+", text) if x.strip()]
        for i, sent in enumerate(sentences):
            if self._stop.is_set():
                break
            audio, rate = self._synth(sent)
            audio = self._robotize(audio, rate)
            self.bus.emit("say", text=sent, dur=len(audio) / rate, first=(i == 0),
                          last=(i == len(sentences) - 1))
            self._play(audio, rate)

    def reset(self):
        self._stop.clear()

    def _play(self, audio, rate, levels=True):
        self.ears.muted = True
        block = int(rate * 0.03)
        try:
            with sd.OutputStream(samplerate=rate, channels=1, dtype="float32") as out:
                for i in range(0, len(audio), block):
                    if self._stop.is_set():
                        break
                    b = audio[i:i + block]
                    if levels:
                        self.bus.emit("level", v=float(min(1.0, np.sqrt(np.mean(b ** 2)) * 4)))
                    out.write(b.reshape(-1, 1))
        finally:
            if levels:
                self.bus.emit("level", v=0)
            self.ears.preroll.clear()         # non riascoltare la propria voce
            self.ears.muted = False

    def stop(self):
        self._stop.set()

    def beep(self, kind="wake"):
        rate = 22050
        notes = {"wake": [880, 1320], "ok": [1320, 880], "error": [300, 220]}[kind]
        parts = []
        for f in notes:
            t = np.arange(int(rate * 0.07)) / rate
            env = np.minimum(1, np.minimum(t, t[::-1]) * 60)
            parts.append(0.25 * np.sin(2 * np.pi * f * t) * env)
        self._play(np.concatenate(parts).astype(np.float32), rate, levels=False)
