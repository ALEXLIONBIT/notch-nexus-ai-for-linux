import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Primo avvio su Windows: dove deve girare il cervello di NEXUS?
Rectangle {
    id: setup
    property Store s
    radius: 26
    color: s.bg
    border.color: Qt.rgba(1, 1, 1, 0.08)
    implicitWidth: 560
    implicitHeight: col.implicitHeight + 64

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 32
        spacing: 18

        Text {
            text: "Benvenuto in NEXUS"
            color: setup.s.ink
            font.family: setup.s.sansFamily; font.pixelSize: 28; font.weight: Font.ExtraBold
        }
        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "Dove deve ragionare il tuo robot? Puoi cambiarlo quando vuoi da Personalizza → Cervello."
            color: setup.s.inkSoft
            font.family: setup.s.sansFamily; font.pixelSize: 15
        }

        Repeater {
            model: [
                { key: "local", title: "Su questo PC (gratis, offline)",
                  body: "Installo Ollama e scarico il cervello più adatto alla tua scheda video. Servono qualche GB e qualche minuto." },
                { key: "provider", title: "Con un provider",
                  body: "Il tuo PC di casa via Tailscale, OpenAI, Claude, Gemini, Groq… Ideale per PC leggeri." }
            ]
            delegate: AbstractButton {
                id: opt
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: box.implicitHeight + 32
                enabled: !setup.s.setup.working
                hoverEnabled: true
                onClicked: {
                    setup.s.setupWantsProvider = modelData.key === "provider"
                    setup.s.setup = { text: modelData.key === "local" ? "Preparo…" : "", pct: -1, done: false, error: "", working: modelData.key === "local" }
                    setup.s.send("setup_choice", { choice: modelData.key })
                }
                background: Rectangle {
                    radius: 18
                    color: opt.hovered ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(1, 1, 1, 0.05)
                    border.width: 1
                    border.color: opt.hovered ? setup.s.led : Qt.rgba(1, 1, 1, 0.08)
                }
                contentItem: Item {
                    implicitHeight: box.implicitHeight
                    ColumnLayout {
                        id: box
                        spacing: 6
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 16
                        Text { text: opt.modelData.title; color: setup.s.led; font.family: setup.s.sansFamily; font.pixelSize: 18; font.weight: Font.Bold }
                        Text {
                            Layout.fillWidth: true; wrapMode: Text.WordWrap
                            text: opt.modelData.body; color: setup.s.inkSoft
                            font.family: setup.s.sansFamily; font.pixelSize: 14
                        }
                    }
                }
            }
        }

        // avanzamento dell'installazione
        ColumnLayout {
            Layout.fillWidth: true
            visible: setup.s.setup.working || setup.s.setup.error !== ""
            spacing: 8
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: setup.s.setup.error !== "" ? "Non ci sono riuscito: " + setup.s.setup.error : setup.s.setup.text
                color: setup.s.setup.error !== "" ? "#ff5a6e" : setup.s.ink
                font.family: setup.s.sansFamily; font.pixelSize: 14
            }
            Rectangle {
                id: track
                Layout.fillWidth: true; height: 8; radius: 4
                visible: setup.s.setup.working
                color: Qt.rgba(1, 1, 1, 0.08)
                clip: true
                Rectangle {
                    height: parent.height; radius: 4; color: setup.s.led
                    width: setup.s.setup.pct >= 0 ? track.width * setup.s.setup.pct / 100 : track.width * 0.3
                    SequentialAnimation on x {
                        running: setup.s.setup.working && setup.s.setup.pct < 0; loops: Animation.Infinite
                        NumberAnimation { from: 0; to: track.width * 0.7; duration: 900 }
                        NumberAnimation { from: track.width * 0.7; to: 0; duration: 900 }
                    }
                }
            }
        }
    }
}
