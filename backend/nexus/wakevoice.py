"""La tua voce come parola di attivazione: registri "Ehi Robot" tre volte e NEXUS confronta il SUONO
(impronte vocali di openWakeWord + DTW), non il testo trascritto. Così capisce anche la pronuncia italiana
("ehirobot" tutto attaccato) che Whisper scrive "Eto bot" o "e il bot".
Le registrazioni restano solo su questo PC (DATA/wake_voice).
"""
import threading

import numpy as np

from .config import DATA

DIR = DATA / "wake_voice"
RATE = 16000


def _trim(a, thr=500):
    """Toglie il silenzio prima e dopo (blocchi da 20 ms)."""
    b = a[: len(a) // 320 * 320].reshape(-1, 320).astype(np.float32)
    if not len(b):
        return a
    on = np.where(np.sqrt((b ** 2).mean(1)) > thr)[0]
    return a if len(on) == 0 else a[on[0] * 320:(on[-1] + 1) * 320]


def _sdtw(t, s):
    """DTW a sottosequenza: il modello t si allinea con qualunque tratto di s. Distanza coseno media sul percorso."""
    D = 1.0 - t @ s.T
    L, T = D.shape
    acc = np.full((L + 1, T + 1), np.inf)
    acc[0, :] = 0.0
    cnt = np.zeros((L + 1, T + 1))
    for i in range(1, L + 1):
        for j in range(1, T + 1):
            best = None
            for a, c in ((acc[i - 1, j - 1], cnt[i - 1, j - 1]), (acc[i - 1, j], cnt[i - 1, j]), (acc[i, j - 1], cnt[i, j - 1])):
                if not np.isfinite(a):
                    continue
                sc = a / max(c, 1)
                if best is None or sc < best[0]:
                    best = (sc, a, c)
            acc[i, j] = best[1] + D[i - 1, j - 1]
            cnt[i, j] = best[2] + 1
    j = int(np.argmin(acc[L, 1:] / np.maximum(cnt[L, 1:], 1))) + 1
    return float(acc[L, j] / cnt[L, j])


class VoiceMatcher:
    def __init__(self):
        self._feat = None
        self._lock = threading.Lock()
        self.templates = []          # sequenze di impronte normalizzate
        self.lengths = []            # durata in secondi di ogni registrazione
        self.strict = self.loose = 0.0
        self.load()

    def _features(self):
        if self._feat is None:
            with self._lock:
                if self._feat is None:
                    from openwakeword.utils import AudioFeatures, download_models
                    try:
                        download_models([])
                    except Exception:
                        pass
                    self._feat = AudioFeatures(inference_framework="onnx")
        return self._feat

    def embed(self, a, template=False):
        a = _trim(a) if template else a
        a = np.concatenate([np.zeros(8000, np.int16), a.astype(np.int16), np.zeros(1280 if template else 4000, np.int16)])
        if len(a) < RATE:
            a = np.concatenate([a, np.zeros(RATE - len(a), np.int16)])
        a = a[: len(a) // 1280 * 1280]
        e = self._features().embed_clips(a[None, :], batch_size=1)[0]
        return e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-8)

    @property
    def ready(self):
        return len(self.templates) >= 2

    def load(self):
        self.templates, self.lengths = [], []
        if not DIR.exists():
            return
        clips = [np.load(f) for f in sorted(DIR.glob("clip*.npy"))]
        if len(clips) < 2:
            return
        self.templates = [self.embed(c, template=True) for c in clips]
        self.lengths = [len(_trim(c)) / RATE for c in clips]
        pair = [_sdtw(a, b) for i, a in enumerate(self.templates) for j, b in enumerate(self.templates) if i != j]
        m = max(pair)
        # soglie tarate sulle tue registrazioni: vicinissimo = sveglio subito; vicino = solo se il testo conferma
        self.strict = max(0.03, m * 1.25)
        self.loose = max(0.06, m * 2.4)
        print(f"voce registrata: {len(clips)} prove, soglie {self.strict:.3f} / {self.loose:.3f}")

    def save(self, clips):
        DIR.mkdir(parents=True, exist_ok=True)
        for f in DIR.glob("clip*.npy"):
            f.unlink()
        for i, c in enumerate(clips):
            np.save(DIR / f"clip{i}.npy", c.astype(np.int16))
        self.load()

    def clear(self):
        for f in DIR.glob("clip*.npy") if DIR.exists() else []:
            f.unlink()
        self.templates, self.lengths = [], []

    def distance(self, audio_int16):
        s = self.embed(audio_int16)
        return min(_sdtw(t, s) for t in self.templates)
