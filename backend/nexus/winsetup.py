"""Primo avvio su Windows: installa Ollama e scarica un cervello adatto a questo PC."""
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path

from .osys import run, popen

OLLAMA_URL = "http://127.0.0.1:11434"


def find_ollama():
    exe = shutil.which("ollama")
    if exe:
        return exe
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
        p = Path(base) / "Programs/Ollama/ollama.exe" if base else None
        if p and p.exists():
            return str(p)
        p = Path(base) / "Ollama/ollama.exe" if base else None
        if p and p.exists():
            return str(p)
    return None


def server_up():
    try:
        urllib.request.urlopen(OLLAMA_URL + "/api/version", timeout=3).read()
        return True
    except Exception:
        return False


def vram_mb():
    try:
        out = run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                  capture_output=True, text=True, timeout=10).stdout
        return max(int(x) for x in out.split())
    except Exception:
        return 0


def pick_model():
    """Il modello più capace che entra nella GPU (senza GPU: il più piccolo, va anche sul processore)."""
    v = vram_mb()
    if v >= 10000:
        return "qwen3.5:9b"
    if v >= 5000:
        return "qwen3.5:4b"
    return "qwen3.5:2b"


def install_ollama(status):
    if shutil.which("winget"):
        status("Installo Ollama con winget…")
        r = run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--silent", "--accept-package-agreements",
                 "--accept-source-agreements", "--disable-interactivity"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=1800)
        if find_ollama():
            return
        print("winget non ha installato Ollama:", (r.stdout or r.stderr)[-300:])
    status("Scarico Ollama…")
    from .config import CACHE
    dest = CACHE / "OllamaSetup.exe"
    req = urllib.request.Request("https://ollama.com/download/OllamaSetup.exe", headers={"User-Agent": "nexus-assistant"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    status("Installo Ollama…")
    run([str(dest), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=1800)
    if not find_ollama():
        raise RuntimeError("non sono riuscito a installare Ollama: scaricalo da ollama.com e riprova")


def install_local_brain(status):
    exe = find_ollama()
    if not exe:
        install_ollama(status)
        exe = find_ollama()
    if not server_up():
        status("Avvio Ollama…")
        popen([exe, "serve"])
        for _ in range(60):
            if server_up():
                break
            time.sleep(1)
        else:
            raise RuntimeError("Ollama è installato ma non risponde")
    model = pick_model()
    status(f"Scarico il cervello {model}…", 0)
    req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=json.dumps({"model": model}).encode(),
                                 headers={"Content-Type": "application/json"})
    last = -1
    with urllib.request.urlopen(req, timeout=3600) as r:
        for line in r:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("error"):
                raise RuntimeError(ev["error"])
            total, done = ev.get("total") or 0, ev.get("completed") or 0
            if total:
                pct = int(done * 100 / total)
                if pct != last:
                    last = pct
                    status(f"Scarico il cervello {model}… {pct}%", pct)
    return model
