#!/usr/bin/env bash
# Installa NEXUS — Notch AI for Linux.
# Funziona su Arch/CachyOS (pacman) e su Ubuntu/Linux Mint/Debian (apt).
#   ./scripts/install.sh                 installazione completa (cervello locale con Ollama)
#   NEXUS_NO_OLLAMA=1 ./scripts/install.sh   PC leggero: niente Ollama, poi scegli un provider online o in rete
#   NEXUS_NO_IMAGES=1 ./scripts/install.sh   senza il modello di immagini (Z-Image-Turbo, ~6,5 GB)
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
VOICES="$HOME/.local/share/nexus/voices"
MODEL="${NEXUS_MODEL:-qwen3.5:4b}"
DESKTOP="${XDG_CURRENT_DESKTOP:-}"

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }

# ------------------------------------------------------------------ pacchetti di sistema
if command -v pacman >/dev/null; then
    say "Pacchetti di sistema (pacman)"
    PKGS="sox uv pyside6 layer-shell-qt wl-clipboard tesseract tesseract-data-ita tesseract-data-eng spectacle avahi"
    [ -z "${NEXUS_NO_OLLAMA:-}" ] && PKGS="$PKGS ollama"
    command -v nvidia-smi >/dev/null && [ -z "${NEXUS_NO_OLLAMA:-}" ] && PKGS="$PKGS ollama-cuda"
    sudo pacman -S --needed $PKGS
elif command -v apt-get >/dev/null; then
    say "Pacchetti di sistema (apt: Ubuntu / Linux Mint / Debian)"
    sudo apt-get update
    sudo apt-get install -y curl python3 libportaudio2 tesseract-ocr tesseract-ocr-ita tesseract-ocr-eng \
        wmctrl xdotool xclip wl-clipboard gnome-screenshot avahi-utils libgtk-3-bin flatpak \
        libxcb-cursor0 libegl1
    if ! command -v uv >/dev/null; then
        say "uv (gestore Python)"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    if [ -z "${NEXUS_NO_OLLAMA:-}" ] && ! command -v ollama >/dev/null; then
        say "Ollama (cervello locale)"
        curl -fsSL https://ollama.com/install.sh | sh
    fi
else
    echo "Distribuzione non riconosciuta: installa a mano tesseract, uv, (ollama) e portaudio." >&2
fi

# mouse e tastiera virtuali: l'utente deve poter usare /dev/uinput
if [ ! -w /dev/uinput ]; then
    say "Permessi per mouse/tastiera virtuali (/dev/uinput)"
    echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' | \
        sudo tee /etc/udev/rules.d/60-nexus-uinput.rules >/dev/null
    echo uinput | sudo tee /etc/modules-load.d/nexus-uinput.conf >/dev/null
    sudo modprobe uinput || true
    sudo udevadm control --reload-rules && sudo udevadm trigger /dev/uinput || true
    sudo usermod -aG input "$USER"
    echo "Fatto: serve uscire e rientrare (o riavviare) perché valga il gruppo 'input'."
fi

# ------------------------------------------------------------------ Python
say "Backend (Python 3.11 via uv)"
uv venv -p 3.11 backend/.venv
uv pip install -p backend/.venv/bin/python -r backend/requirements.txt
if command -v nvidia-smi >/dev/null; then
    uv pip install -p backend/.venv/bin/python nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*" || true
fi

if ! [[ "$DESKTOP" == *KDE* ]] || ! python3 -c "import PySide6" 2>/dev/null; then
    say "Interfaccia (PySide6 da pip)"
    uv venv -p 3.11 ui/.venv
    uv pip install -p ui/.venv/bin/python PySide6
fi

say "Modelli wake word"
backend/.venv/bin/python -c "import openwakeword; openwakeword.utils.download_models()"

say "Voci italiane Piper"
mkdir -p "$VOICES"
HF="https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT"
for v in paola/medium/it_IT-paola-medium riccardo/x_low/it_IT-riccardo-x_low; do
    n="$(basename "$v")"
    [ -f "$VOICES/$n.onnx" ] || curl -fL --progress-bar -o "$VOICES/$n.onnx" "$HF/$v.onnx"
    [ -f "$VOICES/$n.onnx.json" ] || curl -fL -s -o "$VOICES/$n.onnx.json" "$HF/$v.onnx.json"
done

say "Whisper (trascrizione)"
backend/.venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')"

if [ -z "${NEXUS_NO_OLLAMA:-}" ] && command -v ollama >/dev/null; then
    say "Cervello locale: $MODEL"
    sudo systemctl enable --now ollama 2>/dev/null || true
    ollama pull "$MODEL"
fi

if [ -z "${NEXUS_NO_IMAGES:-}" ]; then
    say "Immagini: Z-Image-Turbo (stable-diffusion.cpp, ~6,5 GB)"
    IMG="$HOME/.local/share/nexus/image"; mkdir -p "$IMG/bin"
    if [ ! -x "$IMG/bin/sd-cli" ]; then
        URL=$(curl -fsSL https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest \
              | grep -oE 'https://[^"]+Linux-Ubuntu-[0-9.]+-x86_64-vulkan\.zip' | head -1)
        curl -fL --progress-bar -o /tmp/sd.zip "$URL" && unzip -q -o /tmp/sd.zip -d "$IMG/bin" && rm /tmp/sd.zip
        chmod +x "$IMG/bin/sd-cli" || true
    fi
    HF=https://huggingface.co
    [ -f "$IMG/ae.safetensors" ] || curl -fL --progress-bar -o "$IMG/ae.safetensors" "$HF/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors"
    [ -f "$IMG/qwen3-4b-Q4_K_M.gguf" ] || curl -fL --progress-bar -o "$IMG/qwen3-4b-Q4_K_M.gguf" "$HF/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    [ -f "$IMG/z_image_turbo-Q4_0.gguf" ] || curl -fL --progress-bar -o "$IMG/z_image_turbo-Q4_0.gguf" "$HF/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_0.gguf"
fi

if command -v flatpak >/dev/null; then
    say "Streaming su TV (GNOME Network Displays, facoltativo)"
    flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo || true
    flatpak install --user -y flathub org.gnome.NetworkDisplays || true
fi

# ------------------------------------------------------------------ avvio
say "Comandi e avvio automatico"
mkdir -p "$HOME/.local/bin"
ln -sf "$ROOT/scripts/nexus" "$HOME/.local/bin/nexus"
ln -sf "$ROOT/scripts/nexus-ctl" "$HOME/.local/bin/nexus-ctl"
if [[ "$DESKTOP" == *KDE* || "$DESKTOP" == *GNOME* ]]; then
    mkdir -p "$HOME/.config/systemd/user"
    sed "s|%h/nexus|$ROOT|g" systemd/nexus-backend.service > "$HOME/.config/systemd/user/nexus-backend.service"
    sed "s|%h/nexus|$ROOT|g" systemd/nexus-ui.service > "$HOME/.config/systemd/user/nexus-ui.service"
    systemctl --user daemon-reload
    systemctl --user enable --now nexus-backend nexus-ui
else
    # Cinnamon (Linux Mint), MATE, XFCE…: avvio automatico classico
    mkdir -p "$HOME/.config/autostart"
    cat > "$HOME/.config/autostart/nexus.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=NEXUS
Comment=Assistente vocale
Exec=$ROOT/scripts/nexus
X-GNOME-Autostart-enabled=true
DESK
    echo "NEXUS partirà a ogni accesso. Per avviarlo ora: nexus"
fi
echo
echo "Fatto! Se il PC non è potente: Personalizza → Cervello → Aggiungi provider (Ollama su un altro PC, Tailscale o API online)."
