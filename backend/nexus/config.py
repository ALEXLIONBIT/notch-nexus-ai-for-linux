"""Configurazione di NEXUS: valori di default + config.json modificabile dalla UI."""
import json
import threading
from pathlib import Path

import os

from .osys import IS_WIN

import sys

# ~/nexus; nell'app Windows impacchettata: la cartella dei file inclusi (voci, interfaccia)
ROOT = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
if IS_WIN:
    # la cartella del programma non è scrivibile: dati in %LOCALAPPDATA%, impostazioni in %APPDATA%
    DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "NEXUS"
    CACHE = DATA / "cache"
    CONFIG_FILE = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "NEXUS" / "config.json"
else:
    DATA = Path.home() / ".local/share/nexus"
    CACHE = Path.home() / ".cache/nexus"
    # AppImage: la cartella del programma è in sola lettura, le impostazioni vanno in ~/.config
    CONFIG_FILE = (Path.home() / ".config/nexus/config.json") if getattr(sys, "frozen", False) else ROOT / "config.json"
VOICES_DIR = DATA / "voices"

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8765,
    "user_name": "",
    "auto_mode": False,                  # True = niente conferme (resta il blocco dei comandi distruttivi)
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
if IS_WIN:
    DEFAULTS["safe_shell_prefixes"] = ["Get-", "dir", "ls", "whoami", "hostname", "systeminfo", "ipconfig",
                                       "nvidia-smi", "pwd", "type ", "cat ", "echo "]
    DEFAULTS["setup_done"] = False       # primo avvio: scegliere dove gira il cervello

_lock = threading.Lock()


class Config(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        if CONFIG_FILE.exists():
            try:
                self.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            except Exception as e:  # file rotto → default
                print("config.json non valido:", e)
        for d in (DATA, CACHE, VOICES_DIR, CONFIG_FILE.parent):
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
            CONFIG_FILE.write_text(json.dumps(dict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    def public(self):
        keys = ["model", "wake_word", "wake_threshold", "wake_enabled", "voice", "voice_speed",
                "robot_strength", "language", "screen_scale", "browser", "auto_mode", "provider", "stt_mode", "stt_provider",
                "stt_remote_model", "stt_model"] + (["setup_done"] if IS_WIN or getattr(sys, "frozen", False) else [])
        from .providers import public as pub
        out = {k: self[k] for k in keys}
        out["providers"] = [pub(p) for p in self["providers"]]
        out["model"] = self.active_provider().get("model", "")
        return out
