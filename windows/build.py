"""Costruisce NEXUS per Windows: dipendenze → PyInstaller → selftest → installer Inno Setup.

Gira su Windows (GitHub Actions windows-latest o un PC):  python windows\\build.py
  --no-installer   salta Inno Setup        --no-selftest   salta le prove
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / "build"
DIST = HERE / "dist"
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "backend/nexus/__init__.py").read_text()).group(1)
VOICES = ["it_IT-paola-medium"]


def sh(*cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True, **kw)


def deps():
    py = sys.executable
    sh(py, "-m", "pip", "install", "--upgrade", "pip", "wheel")
    sh(py, "-m", "pip", "install", "-r", ROOT / "backend/requirements.txt", "PySide6-Essentials", "pyinstaller")
    # modelli della parola di attivazione dentro il pacchetto openwakeword (così l'app li ha già)
    sh(py, "-c", "import openwakeword; openwakeword.utils.download_models()")


def voices():
    d = BUILD / "voices"
    d.mkdir(parents=True, exist_ok=True)
    for name in VOICES:
        lang, who, q = name.split("-", 2)
        base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang.split('_')[0]}/{lang}/{who}/{q}/{name}"
        for ext in (".onnx", ".onnx.json"):
            if not (d / (name + ext)).exists():
                print("scarico", name + ext, flush=True)
                urllib.request.urlretrieve(base + ext, d / (name + ext))


def version_file():
    v = tuple(int(x) for x in VERSION.split(".")) + (0,)
    (BUILD / "version.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[StringFileInfo([StringTable('041004B0', [
    StringStruct('CompanyName', 'ALEXLIONBIT'), StringStruct('FileDescription', 'NEXUS - assistente vocale'),
    StringStruct('FileVersion', '{VERSION}'), StringStruct('ProductName', 'NEXUS'),
    StringStruct('ProductVersion', '{VERSION}'), StringStruct('OriginalFilename', 'NEXUS.exe')])]),
    VarFileInfo([VarStruct('Translation', [0x0410, 1200])])]
)""", encoding="utf-8")


def pyinstaller():
    shutil.rmtree(DIST / "NEXUS", ignore_errors=True)
    sh(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", DIST, "--workpath", BUILD / "pyi",
       HERE / "nexus.spec")


def selftest():
    exe = DIST / "NEXUS" / "NEXUS.exe"
    out = DIST / "selftest.json"
    env = dict(os.environ, NEXUS_SELFTEST_FILE=str(out), NEXUS_SELFTEST_SHOTS=str(DIST))
    r = subprocess.run([str(exe), "--selftest"], env=env, timeout=1800)
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for k, v in res.items():
        print(("OK  " if v["ok"] else "ERR ") + k, "-", v["detail"][:300])
        if not v["ok"] and v.get("trace"):
            print(v["trace"])
    print("selftest exit code:", r.returncode, flush=True)
    if r.returncode != 0:
        sys.exit("selftest fallito")


def installer():
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    sh(iscc, f"/DAppVersion={VERSION}", HERE / "nexus.iss")
    print("installer:", DIST / f"NEXUS-Setup-{VERSION}.exe")


if __name__ == "__main__":
    os.chdir(HERE)
    BUILD.mkdir(exist_ok=True)
    if "--no-deps" not in sys.argv:
        deps()
    voices()
    version_file()
    pyinstaller()
    if "--no-selftest" not in sys.argv:
        selftest()
    if "--no-installer" not in sys.argv:
        installer()
