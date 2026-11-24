"""Immagini con Z-Image-Turbo (stable-diffusion.cpp), pensato per GPU piccole (6 GB).

Modelli in ~/.local/share/nexus/image (Linux, scaricati da install.sh) o %LOCALAPPDATA%\\NEXUS\\image (Windows,
scaricati al primo uso con install()):
  z_image_turbo-Q4_0.gguf, qwen3-4b-Q4_K_M.gguf, ae.safetensors, bin/sd-cli
"""
import random
import shutil
import time
from pathlib import Path

from .gpu import ExclusiveGPU
from .osys import IS_WIN, run, pictures_dir
from .config import DATA

IMG_DIR = DATA / "image"
HF = "https://huggingface.co"
MODELS = {
    "ae.safetensors": f"{HF}/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
    "qwen3-4b-Q4_K_M.gguf": f"{HF}/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
    "z_image_turbo-Q4_0.gguf": f"{HF}/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_0.gguf",
}


def _bin():
    for name in (("sd-cli.exe", "sd.exe") if IS_WIN else ("sd-cli", "sd")):
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


def install(progress=print):
    """Windows: scarica stable-diffusion.cpp (Vulkan, va su NVIDIA/AMD/Intel) e i modelli (~6,5 GB)."""
    import json
    import urllib.request
    import zipfile
    (IMG_DIR / "bin").mkdir(parents=True, exist_ok=True)

    def get(url, dest, label):
        tmp = dest.with_suffix(dest.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "nexus-assistant"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total, done, last = int(r.headers.get("Content-Length") or 0), 0, 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                done += len(b)
                if total and done * 100 // total >= last + 10:
                    last = done * 100 // total
                    progress(f"{label}: {last}%")
        tmp.replace(dest)
    try:
        _bin()
    except RuntimeError:
        rel = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest",
            headers={"User-Agent": "nexus-assistant"}), timeout=30).read())
        url = next(a["browser_download_url"] for a in rel["assets"] if a["name"].endswith("bin-win-vulkan-x64.zip"))
        z = IMG_DIR / "sd.zip"
        get(url, z, "Programma")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(IMG_DIR / "bin")
        z.unlink()
    for name, url in MODELS.items():
        if not (IMG_DIR / name).exists():
            get(url, IMG_DIR / name, name.split("-")[0].split(".")[0])
    return available()


def output_dir():
    d = pictures_dir() / "NEXUS"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate(prompt, width=1024, height=1024, steps=8, seed=None):
    """Genera un'immagine e ritorna il percorso del PNG."""
    if not available():
        raise RuntimeError("modello di immagini non installato" + ("" if IS_WIN else ": lancia scripts/install.sh"))
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
        r = run(cmd, capture_output=True, text=True, timeout=900, cwd=str(IMG_DIR))
    if r.returncode != 0 or not out.exists():
        tail = (r.stderr or r.stdout)[-400:]
        raise RuntimeError(f"generazione non riuscita: {tail}")
    return out
