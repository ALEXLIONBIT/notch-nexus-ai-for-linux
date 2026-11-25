"""Playwright MCP: NEXUS usa davvero il browser (apre pagine, legge, clicca, scrive, compila moduli).

Avvia `npx @playwright/mcp` (serve Node.js) con il browser predefinito dell'utente:
- Chrome / Edge → quelli installati (canale "chrome" / "msedge")
- Firefox → il Firefox di Playwright (scaricato una volta)
- Brave, Chromium, Vivaldi, Opera… → motore Chrome con il loro eseguibile
Il browser si vede mentre lavora e ha un profilo suo (i login restano tra un avvio e l'altro).
Gli strumenti di Playwright (browser_navigate, browser_snapshot, browser_click…) vengono aggiunti al registro.
"""
import json
import shutil
import subprocess
import threading

from .osys import IS_WIN, NO_WINDOW

# strumenti utili a un assistente vocale (gli altri allungherebbero solo il prompt)
KEEP = {"browser_navigate", "browser_navigate_back", "browser_snapshot", "browser_click", "browser_type",
        "browser_press_key", "browser_select_option", "browser_hover", "browser_wait_for", "browser_tabs",
        "browser_close", "browser_fill_form", "browser_handle_dialog", "browser_find"}
CHROMIUM_LIKE = {"brave": ["brave", "brave-browser", "brave-browser-stable"], "chromium": ["chromium", "chromium-browser"],
                 "vivaldi": ["vivaldi", "vivaldi-stable"], "opera": ["opera"]}
GUIDE = ("\n\nBROWSER: per usare i siti (cercare dentro un sito, cliccare, compilare moduli, leggere una pagina aperta) usa i "
         "tool browser_*: browser_navigate apre l'indirizzo, browser_snapshot mostra la pagina con i riferimenti (ref) degli "
         "elementi, poi browser_click / browser_type / browser_fill_form usano quei ref. Dopo ogni azione guarda il risultato. "
         "Non inserire password o dati di pagamento: per login e acquisti chiedi all'utente di farlo lui nella finestra.")


def default_browser(choice=""):
    """(nome, eseguibile) del browser da usare: quello scelto in Personalizza → Browser, altrimenti il predefinito."""
    ident = (choice or "").lower()
    if not ident:
        try:
            if IS_WIN:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as k:
                    ident = winreg.QueryValueEx(k, "ProgId")[0].lower()
            else:
                ident = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True,
                                       text=True, timeout=5).stdout.strip().lower()
        except Exception:
            ident = ""
    if "firefox" in ident or "librewolf" in ident or "zen" in ident:
        return "firefox", None
    if "edge" in ident or "msedge" in ident:
        return "msedge", None
    for name, exes in CHROMIUM_LIKE.items():
        if name in ident:
            exe = next((shutil.which(e) for e in exes if shutil.which(e)), None)
            if exe:
                return name, exe
    if "chrome" in ident or "google" in ident:
        return "chrome", None
    # niente di riconosciuto: Chrome se c'è, altrimenti Firefox di Playwright
    return ("chrome", None) if (shutil.which("google-chrome") or shutil.which("google-chrome-stable") or IS_WIN) else ("firefox", None)


class BrowserMCP:
    def __init__(self, cfg, status=lambda **k: None):
        self.cfg = cfg
        self.status = status          # status(state=…, browser=…, text=…) → UI
        self.proc = None
        self.tools = []
        self._id = 0
        self._lock = threading.Lock()
        self.browser = ""

    @staticmethod
    def npx():
        found = shutil.which("npx.cmd" if IS_WIN else "npx") or shutil.which("npx")
        if found:
            return found
        # NEXUS avviato come servizio o dal menu: il PATH può non avere Node (nvm, /usr/local, ~/.local)
        import glob
        from pathlib import Path
        home = str(Path.home())
        for pat in (home + "/.nvm/versions/node/*/bin/npx", "/usr/local/bin/npx", home + "/.local/bin/npx",
                    home + "/.volta/bin/npx", "/opt/homebrew/bin/npx", r"C:\Program Files\nodejs\npx.cmd"):
            hits = sorted(glob.glob(pat))
            if hits:
                return hits[-1]
        return None

    def _cmd(self, *args):
        exe = self.npx()
        base = ["cmd", "/c", exe] if IS_WIN else [exe]
        return base + ["-y", "@playwright/mcp@latest", *args]

    def _send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self._id += 1
            msg["id"] = self._id
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Playwright si è chiuso")
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("id") == msg["id"]:
                if "error" in m:
                    raise RuntimeError(m["error"].get("message", "errore"))
                return m.get("result", {})

    def start(self):
        if not self.npx():
            self.status(state="off", browser="", text="Per usare il browser serve Node.js (nodejs.org).")
            return False
        name, exe = default_browser(self.cfg.get("browser", ""))
        self.browser = name
        from .config import CACHE
        out = CACHE / "playwright"
        out.mkdir(parents=True, exist_ok=True)
        args = ["--browser", "chrome" if exe else name, "--output-dir", str(out)]   # non nella cartella di lavoro
        if exe:
            args += ["--executable-path", exe]
        self.status(state="starting", browser=name, text="Avvio Playwright…")
        kw = {"creationflags": NO_WINDOW} if IS_WIN else {"start_new_session": True}
        import os
        env = dict(os.environ)
        env["PATH"] = os.path.dirname(self.npx()) + os.pathsep + env.get("PATH", "")   # anche node accanto a npx
        kw["env"] = env
        self.proc = subprocess.Popen(self._cmd(*args), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8", cwd=str(out), **kw)
        with self._lock:
            self._send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "nexus", "version": "1"}})
            self._send("notifications/initialized", notify=True)
            self.tools = [t for t in self._send("tools/list").get("tools", []) if t["name"] in KEEP]
        self.status(state="ready", browser=name, text=f"Pronto con {name}: {len(self.tools)} strumenti")
        return True

    def call(self, name, args, _retry=True):
        with self._lock:
            if self.proc is None or self.proc.poll() is not None:
                raise RuntimeError("Playwright non è attivo")
            r = self._send("tools/call", {"name": name, "arguments": args})
        text = "\n".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        if r.get("isError") and "is not installed" in text and _retry:
            self.install()
            return self.call(name, args, _retry=False)
        if len(text) > 7000:
            text = text[:7000] + "\n…(pagina accorciata: usa browser_find o browser_snapshot su una parte)"
        return ("ERRORE: " if r.get("isError") else "") + text

    def install(self):
        """Scarica il browser di Playwright la prima volta (Firefox ~90 MB)."""
        self.status(state="starting", browser=self.browser, text=f"Scarico {self.browser} per Playwright (una volta sola)…")
        kw = {"creationflags": NO_WINDOW} if IS_WIN else {}
        subprocess.run(self._cmd("install-browser", self.browser), capture_output=True, timeout=1800, **kw)
        self.status(state="ready", browser=self.browser, text=f"Pronto con {self.browser}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except OSError:
                pass
        self.proc = None
        self.tools = []
        self.status(state="off", browser="", text="Spento")


_ORIGINAL = {}


def _page_text(mcp, limit=3500):
    """Titolo e contenuto della pagina aperta (dallo snapshot di Playwright), per far leggere il cervello."""
    try:
        snap = mcp.call("browser_snapshot", {})
    except Exception as e:
        return f"(non riesco a leggere la pagina: {e})"
    import re
    keep = []
    for line in snap.splitlines():
        t = line.strip()
        # via le righe di sola struttura ("- generic [ref=e5]:", "- /url: /"): restano testi, link, titoli, campi
        if re.fullmatch(r"-\s*(generic|group|list|listitem|region|navigation|main|banner|contentinfo|img|separator)(\s*\[[^\]]*\])*:?", t):
            continue
        if t.startswith("- /url:") or t.startswith("```"):
            continue
        keep.append(t[:300])
    return "\n".join(keep)[:limit]


def register(mcp, registry):
    """Aggiunge gli strumenti di Playwright al registro dei tool del cervello; open_url e web_search
    da qui in poi aprono la pagina nel browser pilotato (così il cervello la legge e può continuare)."""
    import urllib.parse
    label = {"firefox": "Firefox", "chrome": "Chrome", "msedge": "Edge"}.get(mcp.browser, mcp.browser.title())

    def open_url(ctx, url):
        if "://" not in url:
            url = "https://" + url
        ctx.step("🌐", f"Apro {url} in {label}")
        r = mcp.call("browser_navigate", {"url": url})
        if r.startswith("ERRORE"):
            return r
        return f"Ho aperto {url} in {label} (pilotato da te con i tool browser_*). Contenuto:\n" + _page_text(mcp)

    def web_search(ctx, query):
        ctx.step("🔎", f"Cerco: {query}")
        url = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
        r = mcp.call("browser_navigate", {"url": url})
        if r.startswith("ERRORE"):
            return r
        return (f"Ho cercato '{query}' in {label}. Risultati (per aprirne uno usa browser_click con il ref):\n"
                + _page_text(mcp, 4500))

    for name, fn in (("open_url", open_url), ("web_search", web_search)):
        if name in registry:
            _ORIGINAL.setdefault(name, registry[name])
            schema = dict(registry[name][1])
            f = dict(schema["function"])
            f["description"] = ("Apre un sito nel browser e ne legge il contenuto." if name == "open_url"
                                else "Cerca sul web nel browser e legge i risultati.")
            schema["function"] = f
            registry[name] = (fn, schema)

    for t in mcp.tools:
        name = t["name"]

        def fn(ctx, _name=name, **args):
            ctx.step("🌐", _name.replace("browser_", "").replace("_", " "))
            return mcp.call(_name, args)
        schema = dict(t.get("inputSchema") or {"type": "object", "properties": {}})
        schema.pop("$schema", None)
        schema.setdefault("properties", {})
        registry[name] = (fn, {"type": "function", "function": {
            "name": name, "description": (t.get("description") or name)[:400], "parameters": schema}})


def unregister(registry):
    for k in [k for k in registry if k.startswith("browser_")]:
        registry.pop(k, None)
    for name, orig in _ORIGINAL.items():          # open_url / web_search tornano ad aprire il browser normale
        registry[name] = orig
    _ORIGINAL.clear()
