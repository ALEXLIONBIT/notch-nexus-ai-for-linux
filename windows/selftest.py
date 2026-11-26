"""Prova automatica delle app impacchettate: NEXUS.exe --selftest (Windows) e NEXUS.AppImage --selftest (Linux)

Su Linux (CI senza desktop) si saltano le prove che pilotano finestre, Blocco note e PowerShell.

Prova i pezzi veri sul Windows dove gira (GitHub Actions o un PC): app, finestre, mouse e tastiera, OCR,
PowerShell, voce, trascrizione, wake word, cervello (con un finto provider OpenAI) e interfaccia QML.
Scrive il risultato in NEXUS_SELFTEST_FILE (JSON) e ritorna 0 se tutto è andato bene.
"""
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

RESULTS = {}
OUT = Path(os.environ.get("NEXUS_SELFTEST_FILE") or Path.cwd() / "selftest.json")
SHOTS = Path(os.environ.get("NEXUS_SELFTEST_SHOTS") or Path.cwd())
OPTIONAL = {"winrt_media", "radio", "camera", "volume", "brightness"}   # dipendono dall'hardware del PC
IS_WIN = sys.platform == "win32"
WIN_ONLY = {"folders", "apps_scan", "open_app_and_windows", "type_and_ocr", "click_text", "window_actions",
            "look_screen", "powershell", "clipboard", "volume", "winrt_media", "radio"}
if not IS_WIN:
    OPTIONAL |= {"files"}                     # il cestino dipende dal desktop


WATCHDOG = 300           # secondi: una prova che si pianta salva dove si è fermata e chiude


def check(name):
    def deco(fn):
        if not IS_WIN and name in WIN_ONLY:
            return fn
        import faulthandler
        t0 = time.time()
        hang = open(SHOTS / f"selftest-hang-{name}.txt", "w")
        faulthandler.dump_traceback_later(WATCHDOG, exit=True, file=hang)
        try:
            detail = fn()
            RESULTS[name] = {"ok": True, "detail": str(detail)[:400], "s": round(time.time() - t0, 1)}
        except Exception as e:
            RESULTS[name] = {"ok": False, "detail": f"{type(e).__name__}: {e}"[:400],
                             "trace": traceback.format_exc()[-1200:], "s": round(time.time() - t0, 1)}
        faulthandler.cancel_dump_traceback_later()
        hang.close()
        Path(hang.name).unlink(missing_ok=True)
        print(("OK  " if RESULTS[name]["ok"] else "ERR ") + name, "-", RESULTS[name]["detail"][:200], flush=True)
        OUT.write_text(json.dumps(RESULTS, indent=1, ensure_ascii=False), encoding="utf-8")
        return fn
    return deco


class Ctx:
    def __init__(self, cfg):
        self.cfg = cfg
        self.steps = []
        self.n = type("N", (), {"bus": type("B", (), {"emit": staticmethod(lambda *a, **k: None)})(),
                                "voice": None})()

    def step(self, icon, text):
        self.steps.append(text)

    def image(self, path):
        pass

    def confirm(self, q):
        return True


def main():
    os.environ.setdefault("NEXUS_SELFTEST", "1")
    from nexus.config import Config
    cfg = Config()
    cfg["auto_mode"] = True
    ctx = Ctx(cfg)
    from nexus.tools import Tools, REGISTRY
    tools = Tools(ctx)

    @check("tools_registered")
    def _():
        assert len(REGISTRY) >= 45, len(REGISTRY)
        return f"{len(REGISTRY)} tool"

    @check("folders")
    def _():
        from nexus import osys
        d, p = osys.desktop_dir(), osys.pictures_dir()
        assert d.exists(), d
        return f"desktop={d} immagini={p} sistema={osys.os_name()}"

    @check("apps_scan")
    def _():
        from nexus.tools.apps import scan_apps, find_app, list_browsers
        apps = scan_apps()
        assert len(apps) > 5, len(apps)
        np_ = find_app("blocco note") or find_app("notepad")
        assert np_, "Blocco note non trovato"
        return f"{len(apps)} app, notepad={np_['name']}, browser={[b['name'] for b in list_browsers()]}"

    @check("open_app_and_windows")
    def _():
        r = tools.call("open_app", {"name": "notepad"}).text
        for _ in range(30):
            time.sleep(0.5)
            if "notepad" in tools.call("list_windows", {}).text.lower() or "blocco" in tools.call("list_windows", {}).text.lower():
                break
        lw = tools.call("list_windows", {}).text
        assert "notepad" in lw.lower() or "blocco" in lw.lower(), lw
        pw = tools.call("place_window", {"app": "notepad", "position": "sinistra"}).text
        return f"{r} | {pw} | {lw[:200]}"

    @check("type_and_ocr")
    def _():
        from nexus.tools.screen import screenshot, ocr, find_text
        time.sleep(1)
        tools.call("click", {"x": 250, "y": 500})
        tools.call("type_text", {"text": "NEXUS prova perché città"})
        time.sleep(1.2)
        shot = screenshot()
        import shutil
        shutil.copy(shot, SHOTS / "selftest-notepad.png")
        lines = ocr(shot)
        pos, score = find_text(lines, "NEXUS prova")
        assert pos, f"testo non trovato con l'OCR (migliore {score:.2f}); letto: {[l['text'] for l in lines][:30]}"
        return f"OCR {len(lines)} righe, trovato '{pos[2]}' in {pos[:2]}"

    @check("click_text")
    def _():
        return tools.call("click_text", {"text": "NEXUS prova"}).text

    @check("window_actions")
    def _():
        a = tools.call("window_action", {"app": "notepad", "action": "massimizza"}).text
        b = tools.call("window_action", {"app": "notepad", "action": "riduci"}).text
        c = tools.call("window_action", {"app": "notepad", "action": "attiva"}).text
        import psutil
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower() == "notepad.exe":
                p.kill()
        return " | ".join((a, b, c))

    @check("look_screen")
    def _():
        r = tools.call("look_screen", {"read_text": True})
        assert r.image and Path(r.image).exists()
        return r.text[:200]

    @check("powershell")
    def _():
        r = tools.call("run_shell", {"command": "Get-Date -Format yyyy; cd $env:TEMP"}).text
        assert "exit 0" in r and time.strftime("%Y") in r, r
        r2 = tools.call("run_shell", {"command": "Write-Output (Get-Location).Path"}).text
        assert "temp" in r2.lower(), r2
        blocked = tools.call("run_shell", {"command": "Format-Volume -DriveLetter C"}).text
        assert "bloccato" in blocked.lower(), blocked
        return r.splitlines()[0] + " | cwd ricordata | comando pericoloso bloccato"

    @check("clipboard")
    def _():
        tools.call("clipboard", {"action": "scrivi", "text": "àèìòù NEXUS"})
        r = tools.call("clipboard", {"action": "leggi"}).text
        assert r == "àèìòù NEXUS", r
        return r

    @check("system_info")
    def _():
        return tools.call("system_info", {}).text

    @check("volume")
    def _():
        return tools.call("set_volume", {"percent": 35}).text

    @check("files")
    def _():
        d = Path(os.environ.get("TEMP", ".")) / "nexus-selftest"
        d.mkdir(exist_ok=True)
        w = tools.call("write_file", {"path": str(d / "nota.txt"), "content": "ciao è"}).text
        r = tools.call("read_text_file", {"path": str(d / "nota.txt")}).text
        assert r == "ciao è", r
        f = tools.call("find_files", {"pattern": "nota", "folder": str(d)}).text
        t = tools.call("move_to_trash", {"path": str(d / "nota.txt")}).text
        return f"{w} | {f} | {t}"

    @check("processes")
    def _():
        return tools.call("processes", {}).text[:200]

    @check("winrt_media")
    def _():
        return tools.call("media_control", {"action": "info"}).text

    @check("radio")
    def _():
        from nexus.tools.extra import _win_radio  # noqa: F401
        return "modulo Radios caricato"

    @check("web")
    def _():
        r = tools.call("read_webpage", {"url": "https://example.com"}).text
        assert "Example Domain" in r, r[:200]
        return r[:80]

    @check("tts_piper")
    def _():
        from nexus.tts import Voice
        bus = type("B", (), {"emit": staticmethod(lambda *a, **k: None)})()
        ears = type("E", (), {"muted": False, "preroll": []})()
        v = Voice(cfg, bus, ears)
        assert v.voice is not None, "voce non caricata"
        audio, rate = v._synth("Ciao, sono Nexus. Apri il blocco note.")
        import numpy as np
        robot = v._robotize(audio, rate)                         # prova anche il filtro robot
        import wave
        pcm = (audio * 32767).astype(np.int16)
        with wave.open(str(SHOTS / "selftest-voce.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())
        return f"{len(audio) / rate:.1f} s di voce a {rate} Hz ({len(robot)} campioni col filtro robot)"

    @check("stt_whisper")
    def _():
        import numpy as np
        import wave
        from nexus.stt import Stt
        with wave.open(str(SHOTS / "selftest-voce.wav")) as w:
            rate = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        n = int(len(x) * 16000 / rate)                       # ricampiona a 16 kHz
        x16 = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.int16)
        c = dict(cfg)
        c["stt_model"] = os.environ.get("NEXUS_SELFTEST_WHISPER", "tiny")

        class Cfg(dict):
            def get_provider(self, pid): return None
        st = Stt(Cfg(c))
        text = st.transcribe(x16)
        assert any(w in text.lower() for w in ("ciao", "nexus", "blocco", "note")), text
        return f"{st.device}: “{text}”"

    @check("wake_word")
    def _():
        import numpy as np
        from openwakeword.model import Model
        from openwakeword.utils import download_models
        try:
            download_models(["hey_jarvis"])
        except Exception:
            pass
        m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        s = m.predict(np.zeros(1280, dtype=np.int16))
        return f"modello pronto, punteggi {s}"

    @check("microphone_api")
    def _():
        import sounddevice as sd
        return f"PortAudio {sd.get_portaudio_version()[1]}, dispositivi: {len(sd.query_devices())}"

    @check("brain_with_fake_provider")
    def _():
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        calls = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_GET(self):
                self._json({"object": "list", "data": [{"id": "finto", "object": "model"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(body)
                has_tool_result = any(m.get("role") == "tool" for m in body["messages"])
                if not has_tool_result:
                    delta = {"role": "assistant", "content": None, "tool_calls": [
                        {"index": 0, "id": "call_1", "type": "function",
                         "function": {"name": "system_info", "arguments": "{}"}}]}
                else:
                    delta = {"role": "assistant", "content": "Il PC sta benissimo."}
                chunk = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "finto",
                         "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
                end = {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "finto",
                       "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
                data = f"data: {json.dumps(chunk)}\n\ndata: {json.dumps(end)}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json(self, o):
                d = json.dumps(o).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        cfg["providers"] = [{"id": "finto", "name": "Finto", "preset": "custom", "kind": "openai",
                             "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "api_key": "x", "model": "finto"}]
        cfg["provider"] = "finto"
        from nexus.brain import Brain
        reply = Brain(cfg, tools, ctx).run("come sta il computer?")
        srv.shutdown()
        assert reply == "Il PC sta benissimo.", reply
        sysmsg = calls[0]["messages"][0]["content"]
        assert ("Windows" if IS_WIN else "Linux") in sysmsg, sysmsg[:200]
        return f"risposta: {reply} ({len(calls)} chiamate, tool usato: system_info)"

    @check("update_check")
    def _():
        from nexus.main import Nexus
        got = {}
        n = Nexus.__new__(Nexus)
        n.bus = type("B", (), {"emit": staticmethod(lambda t, **d: got.update(d))})()
        n._win_update_check()
        assert not got.get("error"), got
        return got

    @check("ui_qml")
    def _():
        import subprocess
        out = SHOTS / "selftest-ui.json"
        out.unlink(missing_ok=True)
        cmd = [sys.executable, "--selftest-ui"] if getattr(sys, "frozen", False) else \
              [sys.executable, str(Path(__file__).with_name("nexus_win.py")), "--selftest-ui"]
        try:
            subprocess.run(cmd, timeout=120, env=dict(os.environ, NEXUS_SELFTEST_UI_OUT=str(out)))
        except subprocess.TimeoutExpired:
            raise AssertionError("l'interfaccia non si è chiusa entro 2 minuti")
        res = json.loads(out.read_text(encoding="utf-8"))
        assert res["ok"], res["detail"]
        return res["detail"]

    failed = [k for k, v in RESULTS.items() if not v["ok"] and k not in OPTIONAL]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} prove passate", "FALLITE: " + ", ".join(failed) if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


def ui_main():
    """NEXUS.exe --selftest-ui: carica l'interfaccia QML vera (fuori schermo), poi si chiude."""
    import faulthandler
    out = Path(os.environ.get("NEXUS_SELFTEST_UI_OUT") or Path.cwd() / "selftest-ui.json")
    faulthandler.dump_traceback_later(90, exit=True, file=open(out.with_suffix(".hang.txt"), "w"))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    res = {"ok": False, "detail": ""}
    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
        qapp = QGuiApplication(sys.argv[:1])
        qapp.setOrganizationName("nexus")
        qapp.setApplicationName("nexus-ui")
        import app as ui
        warnings = []
        eng = QQmlApplicationEngine()
        eng.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
        eng.rootContext().setContextProperty("nexus", ui.Bridge())
        clip = ui.Clip()
        eng.rootContext().setContextProperty("clip", clip)
        eng.addImportPath(str(ui.HERE / "qml"))
        eng.load(QUrl.fromLocalFile(str(ui.HERE / "qml" / "MainPlain.qml")))
        QTimer.singleShot(1500, lambda: qapp.exit(0))
        qapp.exec()
        bad = [w for w in warnings if "Error" in w or "is not installed" in w or "not found" in w.lower()]
        if not eng.rootObjects():
            res["detail"] = "QML non caricato: " + "; ".join(warnings[:5])
        elif bad:
            res["detail"] = "; ".join(bad[:5])
        else:
            res = {"ok": True, "detail": f"interfaccia caricata, {len(warnings)} avvisi: " + "; ".join(warnings[:3])}
    except Exception as e:
        res["detail"] = f"{type(e).__name__}: {e}"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    os._exit(0)
