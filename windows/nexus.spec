# PyInstaller: NEXUS per Windows (una cartella con NEXUS.exe, poi impacchettata da Inno Setup)
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
TOOLS = ["apps", "desktop", "screen", "inputs", "shell", "system", "windows", "cast", "install", "image",
         "extra", "camera", "aimodels", "_win_input", "_win_windows"]

datas = [
    (os.path.join(ROOT, "ui", "qml"), "ui/qml"),
    (os.path.join(ROOT, "ui", "fonts"), "ui/fonts"),
    (os.path.join(ROOT, "ui", "app.py"), "ui"),
    (os.path.join(SPECPATH, "build", "voices"), "voices"),
    (os.path.join(SPECPATH, "nexus.png"), "."),
]
datas += collect_data_files("openwakeword")          # modelli della parola di attivazione (scaricati prima)
datas += collect_data_files("piper")                 # espeak-ng per la pronuncia
datas += collect_data_files("faster_whisper")        # Silero VAD
datas += collect_data_files("onnxruntime")

hidden = ["nexus.tools." + t for t in TOOLS] + ["nexus.models", "nexus.chats", "nexus.wakename", "nexus.wakevoice", "nexus.desktops", "nexus.tasks", "nexus.deps", "nexus.browsermcp", "nexus.perms", "nexus.winsetup", "nexus.gateway", "selftest", "app"]
hidden += collect_submodules("winrt") + collect_submodules("openwakeword") + collect_submodules("piper")
hidden += ["pycaw.pycaw", "comtypes.stream", "win32timezone", "send2trash", "zeroconf._utils.ipaddress",
           "zeroconf._handlers.answers", "sounddevice", "_sounddevice_data"]

a = Analysis(
    [os.path.join(SPECPATH, "nexus_win.py")],
    pathex=[os.path.join(ROOT, "backend"), os.path.join(ROOT, "ui"), SPECPATH],
    datas=datas,
    binaries=collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime"),
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "torch", "tensorflow", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "evdev"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXUS", console=False,
          icon=os.path.join(SPECPATH, "nexus.ico"), version=os.path.join(SPECPATH, "build", "version.txt"))
coll = COLLECT(exe, a.binaries, a.datas, name="NEXUS", upx=False)
