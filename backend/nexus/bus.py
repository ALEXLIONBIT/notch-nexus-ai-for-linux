"""Canale tra backend e UI: TCP locale, un messaggio JSON per riga."""
import json
import socket
import threading


class Bus:
    def __init__(self, host, port, on_command, on_connect=None):
        self.on_command = on_command
        self.on_connect = on_connect
        self.clients = []
        self.lock = threading.Lock()
        self.srv = socket.create_server((host, port))

    def start(self):
        threading.Thread(target=self._accept, daemon=True, name="bus-accept").start()

    def _accept(self):
        while True:
            conn, _ = self.srv.accept()
            with self.lock:
                self.clients.append(conn)
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()
            if self.on_connect:
                self.on_connect()

    def _read(self, conn):
        try:
            for line in conn.makefile("r", encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.on_command(json.loads(line))
                except Exception as e:
                    print("comando non valido:", e, line[:200])
        except OSError:
            pass
        finally:
            with self.lock:
                if conn in self.clients:
                    self.clients.remove(conn)

    def emit(self, type_, **data):
        msg = (json.dumps({"type": type_, **data}, ensure_ascii=False) + "\n").encode()
        with self.lock:
            for c in list(self.clients):
                try:
                    c.sendall(msg)
                except OSError:
                    self.clients.remove(c)
