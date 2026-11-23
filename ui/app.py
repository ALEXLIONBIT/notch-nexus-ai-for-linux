#!/usr/bin/env python3
"""NEXUS UI: notch in alto + faccia robot a schermo intero (PySide6 di sistema + layer-shell)."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYER_QML = Path("/usr/lib/qt6/qml/org/kde/layershell")
USE_LAYER = os.environ.get("XDG_SESSION_TYPE") == "wayland" and LAYER_QML.exists() \
    and os.environ.get("NEXUS_NO_LAYERSHELL") != "1"
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

    @Slot(str, "QVariantMap")
    def send(self, type_, data):
        if self.connected:
            self.sock.write((json.dumps({"type": type_, **(data or {})}) + "\n").encode())


def main():
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("nexus")
    app.setApplicationName("nexus-ui")
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
