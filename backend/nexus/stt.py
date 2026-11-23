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
            for lib in sorted(glob.glob(os.path.join(loc, "lib", "lib*.so*"))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


class Stt:
    def __init__(self, cfg):
        from faster_whisper import WhisperModel
        self.cfg = cfg
        name = cfg["stt_model"]
        self.model = None
        if cfg.get("stt_device", "auto") in ("auto", "cuda"):
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
            self.model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=12)
            self.device = "cpu"
        print(f"trascrittore pronto: {name} su {self.device}")

    def transcribe(self, audio_int16):
        audio = audio_int16.astype(np.float32) / 32768.0
        segs, _ = self.model.transcribe(
            audio, language=self.cfg["language"], beam_size=5 if self.device == "cuda" else 1,
            vad_filter=True, condition_on_previous_text=False, no_speech_threshold=0.5,
            hotwords="Nexus Google Chrome Firefox desktop Spotify YouTube Konsole Dolphin")
        text = " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.7).strip()
        return "" if HALLUCINATIONS.search(text) else text
