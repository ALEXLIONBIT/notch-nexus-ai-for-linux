"""llama.cpp per i modelli che Ollama non sa far girare (architetture troppo nuove, come Inkling 2).

Come funziona: il cervello resta "Ollama". Se Ollama non riesce a caricare un modello (errore di forma dei tensori,
architettura sconosciuta, memoria della scheda video finita), NEXUS prende gli stessi file del modello che Ollama
ha già scaricato (o un .gguf scelto da te), avvia llama-server su 127.0.0.1:8091 e ci parla con l'API OpenAI.
Se lo ricorda (config "llamacpp_models") e la volta dopo va subito lì.

llama-server: quello scelto in config "llamacpp_bin", altrimenti quello scaricato da NEXUS dalle build ufficiali
(github.com/ggml-org/llama.cpp: CUDA se c'è, altrimenti Vulkan o processore), altrimenti uno trovato nel sistema.
"""
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from .config import DATA
from .osys import IS_WIN, run

RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=8"
HOME = DATA / "llama.cpp"
LOG = DATA / "llama-server.log"
SLOTS = DATA / "llama-cache"   # la parte di domanda già letta (istruzioni + tool), salvata su disco
PORT = 8091
IDLE_STOP = 600                 # secondi senza domande: spegne llama-server e libera la scheda video
UA = {"User-Agent": "nexus-assistant"}
EXE = "llama-server.exe" if IS_WIN else "llama-server"

# errori di Ollama che vogliono dire "questo modello qui non parte": si riprova con llama.cpp
LOAD_ERRORS = re.compile(r"error loading model|wrong shape|check_tensor_dims|unknown model architecture|"
                         r"unsupported (model|architecture)|llama-server (startup failed|process has terminated)|"
                         r"failed to load model|unable to load model|cudaMalloc failed|model requires more system memory|"
                         r"model runner has unexpectedly stopped", re.I)

on_status = None                # callback(testo): NEXUS lo mostra nel notch (impostato da main.py)


def _say(status, text):
    print("llama.cpp:", text)
    cb = status or on_status            # dentro un compito: nei passi del notch; dal telefono: avviso sul PC
    if cb:
        try:
            cb(text)
        except Exception:
            pass


# ---------------------------------------------------------------- il programma (llama-server)
def _ldconfig_has(lib):
    try:
        return lib in run(["ldconfig", "-p"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return False


def variant():
    """Quale build ufficiale scaricare per questo PC (pezzo finale del nome del file)."""
    arm = platform.machine().lower() in ("aarch64", "arm64")
    if IS_WIN:
        cuda = os.environ.get("CUDA_PATH", "")
        if not arm and cuda and glob.glob(os.path.join(cuda, "bin", "**", "cublas64_13.dll"), recursive=True):
            return "bin-win-cuda-13.5-x64.zip"
        return "bin-win-vulkan-arm64.zip" if arm else "bin-win-vulkan-x64.zip"
    nvidia = bool(shutil.which("nvidia-smi")) or os.path.exists("/proc/driver/nvidia/version")
    if nvidia and not arm and _ldconfig_has("libcublas.so.13"):
        return "bin-ubuntu-cuda-13.5-x64.tar.gz"
    if nvidia and not arm and _ldconfig_has("libcublas.so.12"):
        return "bin-ubuntu-cuda-12.8-x64.tar.gz"
    if _ldconfig_has("libvulkan.so.1"):
        return "bin-ubuntu-vulkan-arm64.tar.gz" if arm else "bin-ubuntu-vulkan-x64.tar.gz"
    return "bin-ubuntu-arm64.tar.gz" if arm else "bin-ubuntu-x64.tar.gz"


def latest():
    """(tag, url, nome) dell'ultima build ufficiale per questo PC."""
    want = variant()
    req = urllib.request.Request(RELEASES, headers=UA)
    for r in json.loads(urllib.request.urlopen(req, timeout=20).read()):
        for a in r.get("assets", []):
            if a["name"].startswith("llama-") and a["name"].endswith(want):
                return r["tag_name"], a["browser_download_url"], a["name"]
    raise RuntimeError("nessuna build di llama.cpp per questo PC (" + want + ")")


def _num(tag):
    m = re.search(r"\d+", tag or "")
    return int(m.group()) if m else 0


def managed():
    """(tag, percorso) del llama-server scaricato da NEXUS, o (None, None)."""
    best = None
    for d in HOME.glob("b*"):
        if not d.is_dir() or d.name.endswith(".tmp"):
            continue
        exe = next(iter(d.rglob(EXE)), None)
        if exe and (best is None or _num(d.name) > _num(best[0])):
            best = (d.name, exe)
    return best or (None, None)


def _own_builds():
    """llama.cpp compilati a mano nella cartella home (es. ~/llama.cpp-latest/build/bin/llama-server)."""
    found = [Path(p) for p in glob.glob(str(Path.home() / "llama.cpp*" / "build" / "bin" / EXE))]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def binary(cfg):
    """Il llama-server da usare: (percorso, da_dove) con da_dove config|nexus|own|system, oppure (None, '')."""
    mine = (cfg.get("llamacpp_bin") or "").strip()
    if mine and os.path.isfile(mine):
        return mine, "config"
    tag, exe = managed()
    if exe:
        return str(exe), "nexus"
    own = _own_builds()
    if own:
        return str(own[0]), "own"
    sysbin = shutil.which("llama-server")
    return (sysbin, "system") if sysbin else (None, "")


def version(exe):
    """Numero di build di un llama-server (es. 12833), 0 se non si capisce."""
    try:
        out = run([exe, "--version"], capture_output=True, text=True, timeout=20)
        m = re.search(r"build (\d+)", (out.stdout or "") + (out.stderr or ""))
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def install(status=None):
    """Scarica l'ultima build ufficiale in DATA/llama.cpp/<tag>/ e toglie le vecchie. Ritorna il llama-server."""
    tag, url, name = latest()
    dest = HOME / tag
    exe = next(iter(dest.rglob(EXE)), None) if dest.exists() else None
    if exe:
        return str(exe)
    HOME.mkdir(parents=True, exist_ok=True)
    arch = HOME / name
    _say(status, f"Scarico llama.cpp {tag}…")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(arch, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -1
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            done += len(b)
            if total and (done * 10 // total) != last:
                last = done * 10 // total
                _say(status, f"Scarico llama.cpp {tag}… {done * 100 // total}%")
    tmp = HOME / (tag + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.unpack_archive(str(arch), str(tmp))
    arch.unlink(missing_ok=True)
    tmp.rename(dest)
    exe = next(iter(dest.rglob(EXE)), None)
    if not exe:
        raise RuntimeError("nell'archivio di llama.cpp non c'è " + EXE)
    if not IS_WIN:
        for f in exe.parent.iterdir():
            if f.is_file() and f.name.startswith(("llama-", "rpc-")):
                f.chmod(0o755)
    for old in HOME.glob("b*"):                      # le build vecchie non servono più
        if old != dest and old.is_dir():
            shutil.rmtree(old, ignore_errors=True)
    _say(status, f"llama.cpp {tag} pronto")
    return str(exe)


# ---------------------------------------------------------------- i file del modello
def _ollama_url(cfg):
    for p in cfg.get("providers", []):
        url = p.get("base_url", "")
        if p.get("kind") == "ollama" and any(h in url for h in ("127.0.0.1", "localhost")):
            return url.rstrip("/")
    return "http://127.0.0.1:11434"


def resolve(model, cfg):
    """(gguf, mmproj o None) per un nome di Ollama o un percorso .gguf."""
    path = os.path.expanduser(model)
    if path.lower().endswith(".gguf") and os.path.isfile(path):
        proj = [p for p in glob.glob(os.path.join(os.path.dirname(path), "*.gguf"))
                if "mmproj" in os.path.basename(p).lower()]
        return path, (proj[0] if proj else None)
    body = json.dumps({"model": model}).encode()
    req = urllib.request.Request(_ollama_url(cfg) + "/api/show", data=body, headers={"Content-Type": "application/json"})
    info = json.loads(urllib.request.urlopen(req, timeout=20).read())
    files = [l.split(" ", 1)[1].strip() for l in info.get("modelfile", "").splitlines() if l.startswith("FROM ")]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise RuntimeError(f"non trovo i file di {model}: Ollama li tiene in una cartella che NEXUS non può leggere")
    return files[0], (files[1] if len(files) > 1 else None)


def wants(model, cfg):
    return model in (cfg.get("llamacpp_models") or []) or model.lower().endswith(".gguf")


def remember(model, cfg):
    lst = list(cfg.get("llamacpp_models") or [])
    if model not in lst:
        lst.append(model)
        cfg["llamacpp_models"] = lst
        try:
            cfg.save()
        except Exception:
            pass


def is_load_error(e):
    return bool(LOAD_ERRORS.search(str(e)))


# ---------------------------------------------------------------- il server
def _slot_file(model, ctx):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)[:80] + f"-{ctx}.bin"


def _log_tail():
    try:
        lines = LOG.read_text(errors="replace").splitlines()
        bad = [l for l in lines if re.search(r"\bE\b|error|failed|out of memory", l)]
        return "\n".join((bad or lines)[-6:])
    except OSError:
        return ""


class _Server:
    def __init__(self):
        self.proc = None
        self.model = ""
        self.ctx = 0
        self.saved = False
        self.last = 0.0
        self.lock = threading.RLock()
        threading.Thread(target=self._idle, daemon=True, name="llama-idle").start()

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def _idle(self):
        while True:
            time.sleep(30)
            with self.lock:
                if self.alive() and time.time() - self.last > IDLE_STOP:
                    print(f"llama.cpp: fermo da {IDLE_STOP // 60} minuti, lo spengo")
                    self.stop()

    def stop(self):
        with self.lock:
            if self.alive():
                self.proc.terminate()
                try:
                    self.proc.wait(10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc, self.model = None, ""

    def _start(self, exe, gguf, proj, model, ctx):
        # --no-op-offload: con i pesi in parte nella RAM evita un buffer enorme sulla scheda video
        # (senza, Inkling 2 Mini su una RTX 3060 da 6 GB chiedeva 7 GB in più e non partiva)
        SLOTS.mkdir(parents=True, exist_ok=True)
        args = [exe, "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT), "--jinja", "-c", str(ctx),
                "--no-op-offload", "--alias", model, "--slot-save-path", str(SLOTS)]
        if proj:
            args += ["--mmproj", proj]
        LOG.parent.mkdir(parents=True, exist_ok=True)
        kw = {"creationflags": 0x08000000} if IS_WIN else {"start_new_session": True}
        env = dict(os.environ)
        if not IS_WIN:                                   # le sue librerie stanno accanto al programma; quelle
            from .osys import FROZEN                     # dell'AppImage di NEXUS non devono confonderlo
            here = os.path.dirname(exe)
            env["LD_LIBRARY_PATH"] = here if FROZEN else here + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        with open(LOG, "wb") as log:
            self.proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(exe),
                                         env=env, **kw)
        self.model, self.ctx, self.saved = model, ctx, False
        t0 = time.time()
        while time.time() - t0 < 600:
            if self.proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(1)
        self.stop()
        return False

    def _slot(self, action):
        """Salva o ricarica dal disco la memoria del server (quello che ha già letto della domanda)."""
        name = _slot_file(self.model, self.ctx)
        if action == "restore" and not (SLOTS / name).exists():
            return False
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/slots/0?action={action}",
                                         data=json.dumps({"filename": name}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=120).read()
            return True
        except Exception as e:
            print(f"llama.cpp: {action} della memoria non riuscito: {e}")
            if action == "restore":
                (SLOTS / name).unlink(missing_ok=True)       # salvata con un altro llama.cpp o modello: si rifà
            return False

    def after_answer(self):
        """Dopo la prima risposta salva la memoria su disco: al prossimo avvio la ricarica in pochi secondi."""
        self.last = time.time()
        if self.alive() and not self.saved:
            self.saved = True
            threading.Thread(target=self._slot, args=("save",), daemon=True).start()

    def ensure(self, model, cfg, status=None):
        with self.lock:
            self.last = time.time()
            if self.alive() and self.model == model:
                return
            self.stop()
            gguf, proj = resolve(model, cfg)
            exe, src = binary(cfg)
            if not exe:
                exe, src = install(status), "nexus"
            free_ollama(cfg)
            _say(status, f"Avvio {model} con llama.cpp (la prima volta ci vuole un po')…")
            ctx = int(cfg.get("num_ctx", 16384))
            for c in dict.fromkeys((ctx, min(ctx, 8192), 4096)):
                if self._start(exe, gguf, proj, model, c):
                    if self._slot("restore"):
                        _say(status, f"{model} pronto su llama.cpp (con la memoria di prima)")
                    else:
                        _say(status, f"{model} pronto su llama.cpp: la prima domanda è lenta, le altre no")
                    self.last = time.time()
                    return
                err = _log_tail()
                if src != "nexus" and re.search(r"unknown model architecture|wrong shape|check_tensor_dims", err):
                    _say(status, "Il llama.cpp di questo PC è troppo vecchio per questo modello: scarico quello nuovo")
                    exe, src = install(status), "nexus"
                    if self._start(exe, gguf, proj, model, c):
                        self.last = time.time()
                        return
                    err = _log_tail()
                if not re.search(r"out of memory|failed to allocate", err, re.I):
                    break                                # non è la memoria: con meno contesto non cambia niente
            raise RuntimeError(f"llama.cpp non riesce ad avviare {model}: " + (_log_tail()[-300:] or "errore sconosciuto"))


SERVER = _Server()


def stop():
    SERVER.stop()


def running_model():
    return SERVER.model if SERVER.alive() else ""


def free_ollama(cfg):
    """Toglie da Ollama i modelli caricati: la scheda video serve a llama.cpp."""
    base = _ollama_url(cfg)
    try:
        ps = json.loads(urllib.request.urlopen(base + "/api/ps", timeout=5).read()).get("models", [])
    except Exception:
        return
    for m in ps:
        try:
            body = json.dumps({"model": m["name"], "keep_alive": 0}).encode()
            urllib.request.urlopen(urllib.request.Request(base + "/api/generate", data=body,
                                                          headers={"Content-Type": "application/json"}), timeout=30).read()
        except Exception:
            pass


def chat(model, msgs, tools, is_cancelled, cfg, status=None):
    """Una domanda al modello su llama.cpp (stesso formato dei provider di NEXUS)."""
    from . import gpu
    from .providers import OpenAIProvider
    SERVER.ensure(model, cfg, status)
    gpu.llm_begin()
    try:
        prov = OpenAIProvider({"base_url": f"http://127.0.0.1:{PORT}/v1", "model": model, "api_key": ""}, {})
        prov.client = prov.client.with_options(timeout=900)
        res = prov.chat(msgs, tools, is_cancelled)
        SERVER.after_answer()
        return res
    finally:
        SERVER.last = time.time()
        gpu.llm_end()


def ollama_chat(body, cfg):
    """Il telefono parla a Ollama (/api/chat): stessa domanda girata a llama.cpp, risposta nel formato di Ollama."""
    model = body.get("model", "")
    SERVER.ensure(model, cfg)
    msgs = []
    for m in body.get("messages", []):
        role = m.get("role", "user")
        if role == "tool":
            msgs.append({"role": "tool", "tool_call_id": m.get("tool_call_id") or m.get("tool_name", ""),
                         "content": m.get("content", "")})
        elif role == "assistant" and m.get("tool_calls"):
            msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": [
                {"id": c.get("id") or f"call_{i}", "type": "function",
                 "function": {"name": c["function"]["name"],
                              "arguments": json.dumps(c["function"].get("arguments") or {})}}
                for i, c in enumerate(m["tool_calls"])]})
        elif m.get("images"):
            parts = [{"type": "text", "text": m.get("content", "")}]
            parts += [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in m["images"]]
            msgs.append({"role": role, "content": parts})
        else:
            msgs.append({"role": role, "content": m.get("content", "")})
    req = {"model": model, "messages": msgs, "stream": False}
    if body.get("tools"):
        req["tools"] = body["tools"]
    opts = body.get("options") or {}
    if "temperature" in opts:
        req["temperature"] = opts["temperature"]
    from . import gpu
    gpu.llm_begin()
    try:
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(req).encode(),
                                   headers={"Content-Type": "application/json"})
        out = json.loads(urllib.request.urlopen(r, timeout=900).read())
        SERVER.after_answer()
    finally:
        SERVER.last = time.time()
        gpu.llm_end()
    msg = out["choices"][0]["message"]
    calls = []
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"].get("arguments") or "{}")
        except ValueError:
            args = {}
        calls.append({"function": {"name": c["function"]["name"], "arguments": args}})
    res = {"model": model, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "message": {"role": "assistant", "content": msg.get("content") or ""}, "done": True, "done_reason": "stop"}
    if calls:
        res["message"]["tool_calls"] = calls
    return res
