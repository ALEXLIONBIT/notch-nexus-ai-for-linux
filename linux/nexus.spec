# PyInstaller: NEXUS per Linux (una cartella con NEXUS, poi impacchettata come AppImage da build.sh)
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
TOOLS = ["apps", "desktop", "screen", "inputs", "shell", "system", "windows", "cast", "install", "image",
         "extra", "camera", "aimodels"]

datas = [
    (os.path.join(ROOT, "ui", "qml"), "ui/qml"),
    (os.path.join(ROOT, "ui", "fonts"), "ui/fonts"),
    (os.path.join(ROOT, "ui", "app.py"), "ui"),
    (os.path.join(SPECPATH, "build", "voices"), "voices"),
    (os.path.join(ROOT, "windows", "nexus.png"), "."),
]
datas += collect_data_files("openwakeword")
datas += collect_data_files("piper")
datas += collect_data_files("faster_whisper")
datas += collect_data_files("onnxruntime")

hidden = ["nexus.tools." + t for t in TOOLS] + ["nexus.models", "nexus.chats", "nexus.wakename", "nexus.perms", "nexus.winsetup", "nexus.gateway", "nexus.tailnet", "selftest", "app"]
hidden += collect_submodules("openwakeword") + collect_submodules("piper") + collect_submodules("evdev")
hidden += ["sounddevice", "_sounddevice_data", "certifi"]

# PortAudio non è dentro la ruota di sounddevice su Linux: lo includiamo (build.sh lo installa)
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
for p in ("/usr/lib/x86_64-linux-gnu/libportaudio.so.2", "/usr/lib/libportaudio.so.2"):
    if os.path.exists(p):
        binaries.append((p, "."))
        break

a = Analysis(
    [os.path.join(SPECPATH, "nexus_linux.py")],
    pathex=[os.path.join(ROOT, "backend"), os.path.join(ROOT, "ui"), os.path.join(ROOT, "windows"), SPECPATH],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "torch", "tensorflow", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "win32api", "pycaw", "winrt"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXUS", console=True, strip=False)
coll = COLLECT(exe, a.binaries, a.datas, name="NEXUS", upx=False)
