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

# saluti che devono precedere il nome ("Ehi Robot", "Hey Robot"); "i" e "e" perché Whisper spesso scrive così "ehi"
GREET = {"ehi", "ei", "hey", "hei", "ehy", "ey", "eh", "e", "ai", "hai", "ay", "ok", "okay", "oi", "i", "he", "hej", "ciao"}

# "il robot", "un robot", "del robot": si parla DEL robot, non AL robot
ARTICLES = {"il", "lo", "la", "l", "un", "uno", "una", "gli", "le", "del", "dello", "della", "al", "allo", "alla",
            "col", "nel", "sul", "dal", "the", "a", "an", "my", "mio", "tuo", "questo", "quel", "quello"}
FUSED = {"e", "ei", "i", "ai", "ey", "ae"}                 # suono del saluto attaccato al nome ("eirobot")

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


def _ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def name_words(name):
    """Il nome senza un eventuale saluto scritto dentro ("Hey Robot" → ["robot"])."""
    w = _plain(name)
    while len(w) > 1 and w[0] in GREET:
        w = w[1:]
    return w


def match(text, name, need_greeting=True):
    """(trovato, resto della frase). Il nome deve essere la prima cosa detta, preceduto dal saluto
    ("Ehi Robot", "Hey Robot"): "robot" da solo o "il robot è rotto" NON svegliano."""
    words = _plain(text)
    target = name_words(name)
    if not words or not target:
        return False, ""
    key = "".join(_sound(w) for w in target)
    need = 0.88 if len(key) <= 4 else 0.8
    n = len(target)
    orig = TAGS.sub(" ", text).split()

    def rest(consumed):
        return " ".join(orig[consumed:]).strip(" ,.!?;:")

    # 1) saluto + nome: "ehi robot", "hey, robot", "ok robot"
    if words[0] in GREET or not need_greeting:
        first = 1 if words[0] in GREET else 0
        for size in (n, n + 1, max(1, n - 1)):
            chunk = words[first:first + size]
            if not chunk or chunk[0] in ARTICLES:
                continue
            if _ratio(key, "".join(_sound(w) for w in chunk)) >= need:
                return True, rest(first + len(chunk))
    # 2) saluto e nome fusi in una parola o spezzati male: "eirobot", "heyrobot", "erobot", "irobot"
    if words[0] in ARTICLES or (len(words) > 1 and words[0] in GREET and words[1] in ARTICLES):
        return False, ""
    for size in (1, 2, n + 1):
        chunk = words[:size]
        got = "".join(_sound(w) for w in chunk)
        if len(got) <= len(key):
            continue                                       # niente saluto davanti: "robot" da solo non basta
        pre, tail = got[:len(got) - len(key)], got[len(got) - len(key):]
        if pre in FUSED and _ratio(key, tail) >= need:
            return True, rest(len(chunk))
    return False, ""


class NameSpotter:
    """Decide se una frase breve è "Ehi <nome>":
    1. se hai registrato la tua voce, confronta il suono (vicinissimo → sveglio; lontano → no, senza nemmeno trascrivere);
    2. altrimenti (o se il suono è "abbastanza" vicino) trascrive con Whisper e controlla saluto + nome,
       con la pronuncia italiana e, per le frasi brevi, anche quella inglese."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.voice = None
        self.busy = False
        self._lock = threading.Lock()

    def load(self):
        if self.model is not None:
            return
        with self._lock:
            if self.model is None:
                import os
                from faster_whisper import WhisperModel
                size = self.cfg.get("wake_model") or "base"
                self.model = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=min(4, os.cpu_count() or 2))
                print(f"riconoscimento del nome pronto (whisper {size})")
        if self.voice is None:
            try:
                from .wakevoice import VoiceMatcher
                self.voice = VoiceMatcher()
            except Exception as e:
                print("impronte vocali non disponibili:", e)

    def check(self, audio_int16, on_hit):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._run, args=(audio_int16, on_hit), daemon=True, name="wake-name").start()

    def _text(self, audio, lang):
        # NIENTE suggerimento col nome: su rumore o silenzio Whisper "inventa" il testo suggerito
        segs, _ = self.model.transcribe(audio.astype(np.float32) / 32768.0, language=lang, beam_size=1,
                                        condition_on_previous_text=False, without_timestamps=True, vad_filter=False)
        return " ".join(s.text for s in segs if s.no_speech_prob < 0.6).strip()

    def _run(self, audio, on_hit):
        try:
            self.load()
            name = (self.cfg.get("agent_name") or "Nexus").strip()
            dur = len(audio) / 16000
            vm = self.voice if self.voice is not None and self.voice.ready else None
            d = None
            if vm is not None:
                d = vm.distance(audio)
                k = 1.3 if self.cfg.get("wake_sensitivity") == "high" else 1.0
                if d >= vm.loose * k:
                    return                                   # non somiglia per niente alla tua voce che lo chiama
                if d < vm.strict * k:
                    more = dur > max(vm.lengths) + 0.9       # dopo il nome c'è una domanda
                    print(f"voce riconosciuta (distanza {d:.3f})")
                    on_hit("…" if more else "", audio)
                    return
            text = self._text(audio, self.cfg.get("language", "it"))
            ok, rest = match(text, name)
            if not ok and dur <= 2.5:                        # "Hey Robot" detto all'inglese
                text_en = self._text(audio, "en")
                ok, rest = match(text_en, name)
                text = text_en if ok else text
            if ok:
                print(f"nome sentito: “{text}”" + (f" (voce {d:.3f})" if d is not None else ""))
                on_hit(rest, audio)
        except Exception as e:
            print("riconoscimento del nome:", e)
        finally:
            self.busy = False
