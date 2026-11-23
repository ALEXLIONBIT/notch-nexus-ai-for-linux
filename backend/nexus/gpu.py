"""Vigile della GPU: con 6 GB non possono stare insieme il cervello (Ollama) e il modello di immagini.

- Le chat aspettano se è in corso un'immagine (llm_begin/llm_end).
- Un'immagine aspetta che finiscano le chat, scarica i modelli di Ollama dalla GPU e solo dopo parte.
"""
import json
import subprocess
import threading
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"

_image_lock = threading.Lock()
_llm_ok = threading.Event()
_llm_ok.set()
_inflight = 0
_count_lock = threading.Lock()


def llm_begin(timeout=600):
    _llm_ok.wait(timeout)
    global _inflight
    with _count_lock:
        _inflight += 1


def llm_end():
    global _inflight
    with _count_lock:
        _inflight = max(0, _inflight - 1)


def vram_used_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return -1


def unload_ollama():
    """Toglie dalla GPU tutti i modelli caricati da Ollama."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=10) as r:
            models = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return
    for m in models:
        body = json.dumps({"model": m, "keep_alive": 0}).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/generate", data=body, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            pass


class ExclusiveGPU:
    """with ExclusiveGPU(): ... — usa la GPU da solo (per le immagini)."""
    def __enter__(self):
        _image_lock.acquire()
        _llm_ok.clear()
        t0 = time.time()
        while _inflight > 0 and time.time() - t0 < 180:      # aspetta che finiscano le chat in corso
            time.sleep(0.2)
        unload_ollama()
        t0 = time.time()
        while time.time() - t0 < 30:                          # aspetta che la memoria si liberi davvero
            used = vram_used_mb()
            if used < 0 or used < 1200:
                break
            time.sleep(0.5)
        return self

    def __exit__(self, *exc):
        _llm_ok.set()
        _image_lock.release()
        return False
