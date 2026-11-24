#!/usr/bin/env bash
# Costruisce NEXUS-<versione>-x86_64.AppImage: dipendenze → PyInstaller → selftest → appimagetool.
# Gira su Ubuntu 22.04 (GitHub Actions, così funziona anche sulle distro più vecchie) o su un PC Linux.
#   ./linux/build.sh [--no-deps] [--no-selftest]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
VERSION=$(grep -oP '__version__ = "\K[^"]+' "$ROOT/backend/nexus/__init__.py")
PY="${PYTHON:-python3}"
cd "$HERE"
mkdir -p build dist

if [[ " $* " != *" --no-deps "* ]]; then
    "$PY" -m pip install --upgrade pip wheel
    "$PY" -m pip install -r "$ROOT/backend/requirements.txt" PySide6-Essentials pyinstaller
    "$PY" -c "from openwakeword.utils import download_models; download_models()"
fi

# voce italiana inclusa
mkdir -p build/voices
for n in it_IT-paola-medium; do
    for ext in .onnx .onnx.json; do
        [ -f "build/voices/$n$ext" ] || curl -fsSL -o "build/voices/$n$ext" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/paola/medium/$n$ext"
    done
done

rm -rf dist/NEXUS
"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyi nexus.spec

if [[ " $* " != *" --no-selftest "* ]]; then
    NEXUS_SELFTEST_FILE="$HERE/dist/selftest.json" NEXUS_SELFTEST_SHOTS="$HERE/dist" \
        timeout 1800 dist/NEXUS/NEXUS --selftest
fi

# AppDir → AppImage
APPDIR=build/AppDir
rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/lib"
cp -a dist/NEXUS "$APPDIR/usr/lib/nexus"
cp "$ROOT/windows/nexus.png" "$APPDIR/nexus-assistant.png"
cat > "$APPDIR/nexus-assistant.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=NEXUS
Comment=Assistente vocale con notch e casco robot
Exec=nexus
Icon=nexus-assistant
Terminal=false
Categories=Utility;
X-AppImage-Version=$VERSION
DESK
cat > "$APPDIR/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/nexus/NEXUS" "$@"
RUN
chmod +x "$APPDIR/AppRun"
TOOL=build/appimagetool
[ -x "$TOOL" ] || { curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage; chmod +x "$TOOL"; }
ARCH=x86_64 "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "dist/NEXUS-$VERSION-x86_64.AppImage"
ls -la dist/*.AppImage
