#!/usr/bin/env python3
"""NEXUS UI: notch in alto + faccia robot a schermo intero (PySide6 di sistema + layer-shell)."""
import json
import os
import sys
from pathlib import Path

HERE = Path(os.environ.get("NEXUS_UI_DIR") or Path(__file__).resolve().parent)
LAYER_QML = Path("/usr/lib/qt6/qml/org/kde/layershell")
# nell'AppImage il Qt incluso non può caricare il layer-shell di sistema (versioni diverse): finestre normali
USE_LAYER = os.environ.get("XDG_SESSION_TYPE") == "wayland" and LAYER_QML.exists() \
    and os.environ.get("NEXUS_NO_LAYERSHELL") != "1" and not getattr(sys, "frozen", False)
if USE_LAYER:
    os.environ["QT_WAYLAND_SHELL_INTEGRATION"] = "layer-shell"

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QFontDatabase  # noqa: E402
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

PORT = int(os.environ.get("NEXUS_PORT", "8765"))


class Bridge(QObject):
    event = Signal(str, "QVariant")
    connectedChanged = Signal()

    def __init__(self):
        super().__init__()
        self.sock = QTcpSocket(self)
        self.buf = b""
        self.sock.readyRead.connect(self._read)
        self.sock.stateChanged.connect(lambda *_: self.connectedChanged.emit())
        self.timer = QTimer(self, interval=1500, timeout=self._ensure)
        self.timer.start()
        self._ensure()

    def _ensure(self):
        if self.sock.state() == QAbstractSocket.SocketState.UnconnectedState:
            self.sock.connectToHost("127.0.0.1", PORT)

    def _read(self):
        self.buf += bytes(self.sock.readAll())
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self.event.emit(msg.pop("type", ""), msg)

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self.sock.state() == QAbstractSocket.SocketState.ConnectedState

    @Slot()
    def quit(self):
        """Unico modo per chiudere NEXUS: Personalizza → Esci (Alt+F4 viene ignorato)."""
        # exit() e non quit(): su Qt 6 quit() chiede alle finestre di chiudersi e le nostre rifiutano (per Alt+F4)
        QGuiApplication.instance().exit(0)

    @Slot(str, "QVariantMap")
    def send(self, type_, data):
        if self.connected:
            self.sock.write((json.dumps({"type": type_, **(data or {})}) + "\n").encode())


class WindowKeeper(QObject):
    """Rimette il notch quando sparisce: col coperchio chiuso o in sospensione lo schermo del portatile
    "scompare", KDE chiude le superfici del notch e al ritorno nessuno le ricreava (NEXUS rispondeva ma
    non si vedeva più). Si attiva quando cambiano gli schermi, al risveglio e con un controllo ogni 10 s."""

    def __init__(self, app, root):
        super().__init__()
        self.app, self.root = app, root
        self.misses = 0
        self.last = 0.0
        self.soon = QTimer(self, singleShot=True, interval=2000, timeout=self.revive)
        app.screenAdded.connect(lambda *_: self.soon.start())
        app.screenRemoved.connect(lambda *_: self.soon.start())
        app.primaryScreenChanged.connect(lambda *_: self.soon.start())
        self.watch = QTimer(self, interval=10000, timeout=self.check)
        self.watch.start()
        try:                                             # risveglio dalla sospensione (systemd-logind)
            from PySide6.QtCore import SLOT
            from PySide6.QtDBus import QDBusConnection
            QDBusConnection.systemBus().connect("org.freedesktop.login1", "/org/freedesktop/login1",
                                                "org.freedesktop.login1.Manager", "PrepareForSleep",
                                                self, SLOT("sleeping(bool)"))
        except Exception as e:
            print("sospensione non osservata:", e)

    @Slot(bool)
    def sleeping(self, going):
        if not going:                                    # appena svegliato: lo schermo torna dopo un attimo
            QTimer.singleShot(3000, self.revive)

    def _win(self, name):
        return next((w for w in self.app.topLevelWindows() if w.objectName() == name), None)

    def revive(self):
        prim = self.app.primaryScreen()
        if prim is None or prim not in self.app.screens():
            return                                       # nessuno schermo vero: riprova al prossimo evento
        for name in ("nexusNotch", "nexusFace"):
            w = self._win(name)
            if w is not None and w.screen() is not prim:
                w.setScreen(prim)
        import time
        self.last = time.time()
        print("schermo cambiato: ricreo il notch su", prim.name())
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(self.root, "reviveWindows")
        self.misses = 0

    def check(self):
        notch, face = self._win("nexusNotch"), self._win("nexusFace")
        if notch is None:
            return
        if face is not None and face.isVisible():
            self.misses = 0                              # modalità schermo intero: il notch è nascosto apposta
            return
        scr = notch.screen()
        lost = scr is None or scr not in self.app.screens() or not notch.isVisible() or not notch.isExposed()
        self.misses = self.misses + 1 if lost else 0
        import time
        # due controlli di fila (non un attimo di passaggio) e non più di una volta al minuto
        # (a schermo spento per risparmio energetico il notch non viene disegnato: non serve insistere)
        if self.misses >= 2 and time.time() - self.last > 60:
            self.revive()


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setOrganizationName("nexus")
    app.setApplicationName("nexus-ui")
    # icona giusta nella barra (AppImage): solo se esiste la voce di menu, altrimenti il portale si lamenta nel journal
    if (Path.home() / ".local/share/applications/nexus-assistant.desktop").exists():
        app.setDesktopFileName("nexus-assistant")
    for f in sorted((HERE / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    engine.rootContext().setContextProperty("nexus", bridge)
    engine.addImportPath(str(HERE / "qml"))
    main_qml = "MainLayer.qml" if USE_LAYER else "MainPlain.qml"
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / main_qml)))
    if not engine.rootObjects():
        sys.exit(1)
    keeper = WindowKeeper(app, engine.rootObjects()[0])   # noqa: F841  (deve restare vivo)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
