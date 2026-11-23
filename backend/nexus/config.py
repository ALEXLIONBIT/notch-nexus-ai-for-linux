"""Configurazione di NEXUS: valori di default + config.json modificabile dalla UI."""
import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # ~/nexus
DATA = Path.home() / ".local/share/nexus"
CACHE = Path.home() / ".cache/nexus"
CONFIG_FILE = ROOT / "config.json"
VOICES_DIR = DATA / "voices"

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8765,
    "user_name": "",
    "browser": "",                       # id .desktop del browser ("" = quello di sistema)                     # come ti chiama il robot (opzionale)
    # cervello
    "ollama_host": "http://127.0.0.1:11434",
    "model": "qwen3.5:4b",               # entra tutto in una GPU da 6 GB
    "num_ctx": 16384,
    "max_steps": 12,
    "memory_minutes": 5,
    # provider: dove gira il cervello (vedi providers.py). Vuoto = Ollama locale con "model".
    "providers": [],
    "provider": "local",
    # trascrizione: "local" (Whisper su questo PC) oppure "remote" (API del provider scelto)
    "stt_mode": "local",
    "stt_provider": "",
    "stt_remote_model": "whisper-1",
    # orecchie
    "wake_word": "hey_jarvis",          # hey_jarvis | alexa | hey_mycroft | hey_rhasspy
    "wake_threshold": 0.5,
    "wake_enabled": True,
    "stt_model": "large-v3-turbo",
    "stt_device": "auto",            # auto | cuda | cpu
    "language": "it",
    # voce
    "voice": "it_IT-paola-medium",
    "voice_speed": 1.0,                  # >1 più veloce
    "robot_strength": 0.45,              # 0 = voce normale, 1 = robot pieno
    # schermo / input
    "screen_scale": 1.0,                 # scala di KDE (es. 1.25) per i click
    "safe_shell_prefixes": ["ls", "df", "free", "uptime", "whoami", "date", "cat ", "pwd",
                            "nvidia-smi", "uname", "ps ", "du "],
}

_lock = threading.Lock()


class Config(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        if CONFIG_FILE.exists():
            try:
                self.update(json.loads(CONFIG_FILE.read_text()))
            except Exception as e:  # file rotto → default
                print("config.json non valido:", e)
        for d in (DATA, CACHE, VOICES_DIR):
            d.mkdir(parents=True, exist_ok=True)
        if not self["providers"]:                      # migrazione: il vecchio setup diventa il provider "local"
            from .providers import DEFAULT_PROVIDER
            p = dict(DEFAULT_PROVIDER, base_url=self["ollama_host"], model=self["model"])
            self["providers"] = [p]
            self["provider"] = "local"

    def active_provider(self):
        for p in self["providers"]:
            if p["id"] == self["provider"]:
                return p
        return self["providers"][0]

    def get_provider(self, pid):
        return next((p for p in self["providers"] if p["id"] == pid), None)

    def save(self):
        with _lock:
            CONFIG_FILE.write_text(json.dumps(dict(self), indent=2, ensure_ascii=False))

    def public(self):
        keys = ["model", "wake_word", "wake_threshold", "wake_enabled", "voice", "voice_speed",
                "robot_strength", "language", "screen_scale", "browser", "provider", "stt_mode", "stt_provider",
                "stt_remote_model", "stt_model"]
        from .providers import public as pub
        out = {k: self[k] for k in keys}
        out["providers"] = [pub(p) for p in self["providers"]]
        out["model"] = self.active_provider().get("model", "")
        return out
