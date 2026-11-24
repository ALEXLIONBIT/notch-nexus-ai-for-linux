"""Parola di attivazione = il nome che dai all'agente ("Ehi Marco", "Jarvis", "Nexus"…).

I modelli di openWakeWord riconoscono solo poche frasi già addestrate. Per un nome qualsiasi:
quando il VAD sente una frase breve, Whisper "tiny" la trascrive e un confronto "a orecchio"
cerca il nome fra le prime parole.
Whisper lavora solo quando qualcuno parla, non in continuo.
"""
import difflib
import re
import threading
import unicodedata

import numpy as np

FILLERS = {"ehi", "ei", "hey", "hei", "ehy", "ok", "okay", "ciao", "senti", "oh", "o", "allora", "dai", "e",
           "il", "i", "hai", "ai", "eh", "he"}          # "ehi" a volte viene trascritto così


TAGS = re.compile(r"[\[(][^\])]*[\])]")                     # "[Musica]", "(rumore)": etichette, non parole


def _plain(text):
    text = TAGS.sub(" ", text)
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def _sound(word):
    """Chiave fonetica semplice (italiano/inglese): Nexus ≈ Nexsus ≈ Necsus, Jarvis ≈ Giarvis."""
    w = word
    for a, b in (("ph", "f"), ("gi", "j"), ("ch", "k"), ("ck", "k"), ("qu", "k"), ("x", "ks"), ("y", "i"),
                 ("w", "v"), ("c", "k"), ("q", "k"), ("h", "")):
        w = w.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", w)


def match(text, name):
    """(trovato, resto della frase dopo il nome). Il nome va detto all'inizio (al massimo dopo "ehi", "ok"…)."""
    words = _plain(text)
    target = _plain(name)
    if not words or not target:
        return False, ""
    key = "".join(_sound(w) for w in target)
    need = 0.86 if len(key) <= 4 else 0.78
    n = len(target)
    i = 0
    while i < len(words) and words[i] in FILLERS and i < 3:
        i += 1
    for start in range(i, min(i + 2, len(words))):          # il nome entro le prime parole utili
        for size in (n, n + 1, max(1, n - 1)):              # "nex sus", "nexus" detto in due pezzi…
            chunk = words[start:start + size]
            if not chunk:
                continue
            got = "".join(_sound(w) for w in chunk)
            if difflib.SequenceMatcher(None, key, got).ratio() >= need:
                orig = TAGS.sub(" ", text).split()
                consumed = start + len(chunk)              # riempitivi + nome
                return True, " ".join(orig[consumed:]).strip(" ,.!?;:")
    return False, ""


class NameSpotter:
    """Trascrive le frasi brevi con Whisper tiny (in un thread a parte) e chiama on_hit(resto) se c'è il nome."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.busy = False
        self._lock = threading.Lock()

    def load(self):
        if self.model is not None:
            return
        with self._lock:
            if self.model is None:
                import os
                from faster_whisper import WhisperModel
                self.model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=min(4, os.cpu_count() or 2))
                print("riconoscimento del nome pronto (whisper tiny)")

    def check(self, audio_int16, on_hit):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._run, args=(audio_int16, on_hit), daemon=True, name="wake-name").start()

    def _run(self, audio, on_hit):
        try:
            self.load()
            name = (self.cfg.get("agent_name") or "Nexus").strip()
            # NIENTE suggerimento col nome: su rumore, silenzio o tosse Whisper "inventa" proprio il testo
            # suggerito ("Ehi Marco.") e NEXUS si sveglierebbe da solo. Il confronto fonetico basta.
            segs, _ = self.model.transcribe(audio.astype(np.float32) / 32768.0, language=self.cfg.get("language", "it"),
                                            beam_size=1, condition_on_previous_text=False,
                                            without_timestamps=True, vad_filter=False)
            segs = [s for s in segs if s.no_speech_prob < 0.6]      # Whisper stesso dice che non è parlato
            text = " ".join(s.text for s in segs).strip()
            ok, rest = match(text, name)
            if ok:
                print(f"nome sentito: “{text}”")
                on_hit(rest, audio)
        except Exception as e:
            print("riconoscimento del nome:", e)
        finally:
            self.busy = False
