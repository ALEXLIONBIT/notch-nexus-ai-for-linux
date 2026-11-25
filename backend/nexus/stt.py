"""Voce → testo con faster-whisper large-v3-turbo (GPU se c'è spazio, altrimenti CPU)."""
import ctypes
import glob
import os
import re

import numpy as np

# frasi che whisper "inventa" sul silenzio
HALLUCINATIONS = re.compile(r"(amara\.org|sottotitoli|grazie per la visione|iscriviti al canale|"
                            r"a cura di|qtss|www\.)", re.I)


def _preload_cuda_libs():
    """Carica cuBLAS/cuDNN 12 installati via pip nel venv (il sistema ha CUDA 13)."""
    import importlib.util
    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        spec = importlib.util.find_spec(pkg)
        if not spec or not spec.submodule_search_locations:
            continue
        for loc in spec.submodule_search_locations:
            for lib in sorted(glob.glob(os.path.join(loc, "lib", "lib*.so*")) + glob.glob(os.path.join(loc, "bin", "*.dll"))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def ensure_model(name, progress=None):
    """Percorso del modello Whisper; se non è ancora sul PC lo scarica mostrando l'avanzamento
    (la prima volta sono 1,6 GB: senza barra sembrava che NEXUS fosse bloccato)."""
    import os
    if os.path.isdir(str(name)):
        return name
    from faster_whisper.utils import _MODELS
    from huggingface_hub import snapshot_download
    repo = _MODELS.get(name, name)
    try:
        return snapshot_download(repo, local_files_only=True)
    except Exception:
        pass
    if progress is None:
        return name
    from tqdm.auto import tqdm

    import time as _t
    state = {"big": 0, "t": 0.0}

    class Bar(tqdm):
        def __init__(self, *a, **k):
            k["disable"] = False
            super().__init__(*a, **k)

        def update(self, n=1):
            r = super().update(n)
            tot = self.total or 0
            if tot > 5_000_000:
                state["big"] = max(state["big"], tot)
            # segue solo la barra dei pesi (la più grande) e aggiorna al massimo una volta al secondo
            if tot and tot == state["big"] and _t.time() - state["t"] > 1.0:
                state["t"] = _t.time()
                pct = min(99, int(self.n * 100 / tot))
                progress(f"Scarico il riconoscimento vocale ({name})… {pct}% · {self.n / 1e6:.0f} di {tot / 1e6:.0f} MB", pct)
            return r
    progress(f"Scarico il riconoscimento vocale ({name})… una volta sola", 0)
    return snapshot_download(repo, tqdm_class=Bar)


class Stt:
    """Trascrizione locale (Whisper, caricato solo quando serve) o remota (API del provider)."""
    def __init__(self, cfg, progress=None):
        self.cfg = cfg
        self.progress = progress
        self.model = None
        self.device = "remoto"
        if cfg.get("stt_mode", "local") == "local":
            self._load_local()

    def reset(self):
        self.model = None
        if self.cfg.get("stt_mode", "local") == "local":
            self._load_local()

    def _load_local(self):
        from faster_whisper import WhisperModel
        cfg = self.cfg
        name = ensure_model(cfg["stt_model"], self.progress)
        label = cfg["stt_model"]
        self.model = None
        from .osys import IS_WIN
        # Windows: la GPU solo se scelta apposta (senza le DLL di cuDNN ctranslate2 chiude il programma)
        want = cfg.get("stt_device", "auto")
        if (want == "cuda") or (want == "auto" and not IS_WIN):
            try:
                _preload_cuda_libs()
                self.model = WhisperModel(name, device="cuda", compute_type="int8_float16")
                # prova vera (senza VAD) così l'encoder usa davvero cuBLAS/cuDNN
                noise = (np.random.randn(16000 * 2) * 0.05).astype(np.float32)
                list(self.model.transcribe(noise, language="it", vad_filter=False)[0])
                self.device = "cuda"
            except Exception as e:
                print("whisper su GPU non disponibile, uso la CPU:", str(e)[:120])
                self.model = None
        if self.model is None:
            self.model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(2, (os.cpu_count() or 4) - 2))
            self.device = "cpu"
        print(f"trascrittore pronto: {label} su {self.device}")

    def prompt(self):
        """Suggerimento per Whisper: le parole che l'utente usa davvero (app, TV, comandi)."""
        extra = self.cfg.get("stt_words", "")
        return ("Comandi per l'assistente Nexus: apri Firefox, apri Google Chrome, metti LibreOffice Writer a "
                "sinistra, affianca le finestre, condividi lo schermo sulla TV Cucina, riordina il desktop, "
                "cerca su YouTube. " + extra).strip()

    def _remote(self, audio_int16):
        import wave
        from .config import CACHE
        from .providers import make
        pid = self.cfg.get("stt_provider") or self.cfg["provider"]
        p = self.cfg.get_provider(pid) or self.cfg.active_provider()
        if p.get("kind") == "ollama":
            raise RuntimeError("la trascrizione remota richiede un provider compatibile OpenAI (es. OpenAI o Groq)")
        path = CACHE / "stt.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(audio_int16.tobytes())
        return make(p).transcribe(str(path), self.cfg.get("stt_remote_model") or "whisper-1").strip()

    def transcribe(self, audio_int16):
        if self.cfg.get("stt_mode", "local") == "remote":
            return self._remote(audio_int16)
        if self.model is None:
            self._load_local()
        audio = audio_int16.astype(np.float32) / 32768.0
        peak = float(np.abs(audio).max()) if audio.size else 0.0
        if peak > 1e-3:                                   # volume normalizzato: microfoni bassi capiscono meglio
            audio = audio / peak * 0.9
        segs, _ = self.model.transcribe(
            audio, language=self.cfg["language"], beam_size=3,
            vad_filter=True, condition_on_previous_text=False, no_speech_threshold=0.5,
            initial_prompt=self.prompt())
        text = " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.7).strip()
        if HALLUCINATIONS.search(text) or text.startswith("Comandi per l'assistente"):
            return ""
        return text
