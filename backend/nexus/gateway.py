"""Porta d'ingresso per gli altri dispositivi (telefono, tablet…), su 127.0.0.1:8766.

Esposta solo ai tuoi dispositivi con:  tailscale serve --bg --tcp 11434 tcp://localhost:8766
- /v1/images/generations  → immagini con Z-Image-Turbo (API compatibile OpenAI)
- /nexus/status            → versione di NEXUS e aggiornamenti attorno (Ollama, modelli, sistema) per il telefono
- /nexus/deps_apply        → il telefono chiede di aggiornare i modelli di Ollama su questo PC
- tutto il resto           → inoltrato a Ollama, ma in coda se la GPU sta facendo un'immagine
"""
import base64
import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import gpu, imagegen

SIZES = {"1024x1024": (1024, 1024), "768x1024": (768, 1024), "1024x768": (1024, 768), "512x512": (512, 512)}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    on_image = None          # callback (prompt, path) per mostrare l'immagine anche sul PC
    status_cb = None         # () -> dict: versione e aggiornamenti di questo PC
    apply_cb = None          # (id) -> None: aggiorna una voce (dal telefono solo "models")

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_POST(self):
        if self.path.rstrip("/").endswith("/images/generations"):
            return self._image()
        if self.path.rstrip("/") == "/nexus/deps_apply":
            try:
                what = json.loads(self._body() or b"{}").get("id", "")
            except ValueError:
                what = ""
            if what != "models" or not Handler.apply_cb:      # Ollama e sistema chiedono la password: si fanno dal PC
                return self._send(400, {"ok": False, "error": "dal telefono si possono aggiornare solo i modelli"})
            Handler.apply_cb(what)
            return self._send(200, {"ok": True})
        self._proxy("POST")

    def do_GET(self):
        if self.path.rstrip("/") == "/nexus/status":
            if not Handler.status_cb:
                return self._send(404, {"error": "non disponibile"})
            try:
                return self._send(200, Handler.status_cb())
            except Exception as e:
                return self._send(500, {"error": str(e)[:200]})
        self._proxy("GET")

    def _image(self):
        try:
            req = json.loads(self._body() or b"{}")
            w, h = SIZES.get(req.get("size", "1024x1024"), (1024, 1024))
            path = imagegen.generate(req.get("prompt", ""), w, h)
            if Handler.on_image:
                Handler.on_image(req.get("prompt", ""), str(path))
            b64 = base64.b64encode(path.read_bytes()).decode()
            self._send(200, {"created": int(time.time()), "data": [{"b64_json": b64}]})
        except Exception as e:
            self._send(500, {"error": {"message": str(e)[:300]}})

    def _proxy(self, method):
        body = self._body() if method == "POST" else None
        gpu.llm_begin()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=600)
            conn.request(method, self.path, body=body, headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
            r = conn.getresponse()
            data = r.read()
            self._send(r.status, data, r.getheader("Content-Type", "application/json"))
        except Exception as e:
            self._send(502, {"error": f"Ollama non risponde: {e}"})
        finally:
            gpu.llm_end()


def start(on_image=None, port=8766):
    Handler.on_image = on_image
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True, name="gateway").start()
    return srv
