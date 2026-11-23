"""Immagini con Z-Image-Turbo (stable-diffusion.cpp), pensato per GPU piccole (6 GB).

Modelli in ~/.local/share/nexus/image (scaricati da install.sh):
  z_image_turbo-Q4_0.gguf, qwen3-4b-Q4_K_M.gguf, ae.safetensors, bin/sd-cli
"""
import random
import shutil
import subprocess
import time
from pathlib import Path

from .gpu import ExclusiveGPU

IMG_DIR = Path.home() / ".local/share/nexus/image"


def _bin():
    for name in ("sd-cli", "sd"):
        for p in (IMG_DIR / "bin" / name, *IMG_DIR.glob(f"bin/**/{name}")):
            if p.exists():
                return p
    found = shutil.which("sd-cli") or shutil.which("sd")
    if found:
        return Path(found)
    raise RuntimeError("stable-diffusion.cpp non è installato (manca sd-cli)")


def available():
    try:
        _bin()
    except RuntimeError:
        return False
    return all((IMG_DIR / f).exists() for f in ("z_image_turbo-Q4_0.gguf", "qwen3-4b-Q4_K_M.gguf", "ae.safetensors"))


def output_dir():
    try:
        pics = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        pics = ""
    d = Path(pics or Path.home() / "Pictures") / "NEXUS"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate(prompt, width=1024, height=1024, steps=8, seed=None):
    """Genera un'immagine e ritorna il percorso del PNG."""
    if not available():
        raise RuntimeError("modello di immagini non installato: lancia scripts/install.sh")
    width, height = (max(256, min(1280, int(v) // 16 * 16)) for v in (width, height))
    out = output_dir() / f"nexus-{time.strftime('%Y%m%d-%H%M%S')}.png"
    cmd = [str(_bin()),
           "--diffusion-model", str(IMG_DIR / "z_image_turbo-Q4_0.gguf"),
           "--llm", str(IMG_DIR / "qwen3-4b-Q4_K_M.gguf"),
           "--vae", str(IMG_DIR / "ae.safetensors"),
           "-p", prompt, "-W", str(width), "-H", str(height),
           "--steps", str(steps), "--cfg-scale", "1.0",
           "--seed", str(seed if seed is not None else random.randint(0, 2**31 - 1)),
           "--offload-to-cpu", "--backend", "te=cpu",
           "-o", str(out)]
    with ExclusiveGPU():
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(IMG_DIR))
    if r.returncode != 0 or not out.exists():
        tail = (r.stderr or r.stdout)[-400:]
        raise RuntimeError(f"generazione non riuscita: {tail}")
    return out
