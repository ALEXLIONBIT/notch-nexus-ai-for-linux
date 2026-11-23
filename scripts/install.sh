#!/usr/bin/env bash
# Installa NEXUS — Notch AI for Linux.
# Pacchetti di sistema (Arch / CachyOS):
#   sudo pacman -S --needed ollama-cuda sox uv layer-shell-qt pyside6 wl-clipboard \
#        tesseract tesseract-data-ita tesseract-data-eng spectacle
#   sudo systemctl enable --now ollama
# Il tuo utente deve poter scrivere su /dev/uinput (gruppo "input") per mouse e tastiera.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
VOICES="$HOME/.local/share/nexus/voices"
MODEL="${NEXUS_MODEL:-qwen3.5:4b}"

echo "== venv backend (Python 3.11 via uv) =="
uv venv -p 3.11 backend/.venv
uv pip install -p backend/.venv/bin/python -r backend/requirements.txt

if command -v nvidia-smi >/dev/null; then
    echo "== librerie CUDA 12 per Whisper su GPU (opzionale) =="
    uv pip install -p backend/.venv/bin/python nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" || true
fi

echo "== modelli wake word =="
backend/.venv/bin/python -c "import openwakeword; openwakeword.utils.download_models()"

echo "== voci italiane Piper =="
mkdir -p "$VOICES"
HF="https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT"
for v in paola/medium/it_IT-paola-medium riccardo/x_low/it_IT-riccardo-x_low; do
    n="$(basename "$v")"
    [ -f "$VOICES/$n.onnx" ] || curl -fL --progress-bar -o "$VOICES/$n.onnx" "$HF/$v.onnx"
    [ -f "$VOICES/$n.onnx.json" ] || curl -fL -s -o "$VOICES/$n.onnx.json" "$HF/$v.onnx.json"
done

echo "== Whisper large-v3-turbo (prima volta) =="
backend/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')"

echo "== cervello: $MODEL =="
ollama pull "$MODEL"

echo "== comandi e servizi =="
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
ln -sf "$ROOT/scripts/nexus" "$HOME/.local/bin/nexus"
ln -sf "$ROOT/scripts/nexus-ctl" "$HOME/.local/bin/nexus-ctl"
sed "s|%h/nexus|$ROOT|g" systemd/nexus-backend.service > "$HOME/.config/systemd/user/nexus-backend.service"
sed "s|%h/nexus|$ROOT|g" systemd/nexus-ui.service > "$HOME/.config/systemd/user/nexus-ui.service"
systemctl --user daemon-reload
echo "Fatto. Avvia con:  systemctl --user enable --now nexus-backend nexus-ui   (oppure: nexus)"
