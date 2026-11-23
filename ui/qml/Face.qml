import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Effects

// Schermo intero: il casco di perla di NEXUS con il visore LED, sottotitoli e barra per scrivere.
Rectangle {
    id: face
    required property var store
    readonly property var s: store
    color: s.bg
    focus: true
    Keys.onEscapePressed: s.editorOpen ? s.editorOpen = false : s.settingsOpen ? s.settingsOpen = false : s.fullscreen = false

    // luce morbida dall'alto
    Shape {
        anchors.fill: parent
        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: face.width / 2; centerY: face.height * 0.36
                centerRadius: face.width * 0.62
                focalX: centerX; focalY: centerY
                GradientStop { position: 0; color: face.s.bgGlow }
                GradientStop { position: 1; color: face.s.bgDeep }
            }
            PathRectangle { x: 0; y: 0; width: face.width; height: face.height }
        }
    }

    // marchio discreto
    Text {
        x: 44; y: 34
        text: "nexus"
        color: face.s.inkSoft
        font { family: face.s.dotFamily; pixelSize: 26; weight: Font.Black }
    }
    Row {
        anchors { right: parent.right; top: parent.top; margins: 30 }
        spacing: 6
        IconButton { glyph: "gear"; tip: "Personalizza"; tint: face.s.ink; size: 40
            onClicked: face.s.settingsOpen = !face.s.settingsOpen }
        IconButton { glyph: "close"; tip: "Esci (Esc)"; tint: face.s.ink; size: 40
            onClicked: face.s.fullscreen = false }
    }

    Decorations { store: face.s; anchors.fill: parent }

    // ---------- il casco ----------
    Helmet {
        id: helmet
        store: face.s
        width: Math.min(face.width * 0.46, 860) * (shape.aspect > 0.7 ? 0.72 : 1)
        anchors.horizontalCenter: parent.horizontalCenter
        y: face.height * 0.40 - height / 2
    }

    // ---------- stato + sottotitoli ----------
    ColumnLayout {
        id: talk
        anchors.horizontalCenter: parent.horizontalCenter
        y: helmet.y + helmet.height + face.height * 0.07
        width: Math.min(face.width * 0.62, 980)
        spacing: 14

        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            Rectangle {
                width: 9; height: 9; radius: 5
                anchors.verticalCenter: parent.verticalCenter
                color: face.s.stateColor
            }
            Text {
                text: face.s.st === "acting" && face.s.steps.count > 0
                      ? face.s.steps.get(face.s.steps.count - 1).text : face.s.statusText
                color: face.s.inkSoft
                font { family: face.s.sansFamily; pixelSize: 17; weight: Font.Medium }
            }
        }

        Subtitle {
            store: face.s
            visible: face.s.sayText !== ""
            litColor: face.s.ink
            dimColor: Qt.rgba(face.s.inkSoft.r, face.s.inkSoft.g, face.s.inkSoft.b, 0.38)
            font { family: face.s.dotFamily; pixelSize: Math.max(30, face.width * 0.019); weight: Font.Black }
            horizontalAlignment: Text.AlignHCenter
            lineHeight: 1.1
            Layout.fillWidth: true
        }
        Text {
            visible: face.s.sayText === "" && face.s.reply !== ""
            text: face.s.reply
            color: face.s.ink
            font { family: face.s.dotFamily; pixelSize: Math.max(30, face.width * 0.019); weight: Font.Black }
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Text {
            visible: face.s.transcript !== ""
            text: "Tu: " + face.s.transcript
            color: face.s.inkSoft
            font { family: face.s.sansFamily; pixelSize: 16 }
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        RowLayout {
            visible: face.s.confirmText !== ""
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            Text { text: face.s.confirmText; color: face.s.ink; font { family: face.s.sansFamily; pixelSize: 18; weight: Font.DemiBold } }
            IconButton { text: "Sì, procedi"; size: 40; tint: "#1a1306"; fill: face.s.thinkAmber
                onClicked: face.s.send("confirm", { id: face.s.confirmId, ok: true }) }
            IconButton { text: "No"; size: 40; tint: face.s.ink; fill: face.s.dark ? "#2a2e35" : "#dde2e7"
                onClicked: face.s.send("confirm", { id: face.s.confirmId, ok: false }) }
        }
    }

    // ---------- barra per scrivere ----------
    Rectangle {
        id: bar
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 44 }
        width: Math.min(face.width * 0.5, 820); height: 60; radius: 30
        color: face.s.dark ? "#22262c" : "#ffffff"
        layer.enabled: true
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: face.s.shellShadow; shadowOpacity: 0.3; shadowBlur: 0.8; blurMax: 32; shadowVerticalOffset: 8; shadowHorizontalOffset: 0 }

        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 10
            spacing: 8
            readonly property bool busy: face.s.st !== "idle" && face.s.st !== "loading"
            IconButton {
                size: 44
                glyph: parent.busy ? "stop" : "mic"
                tip: parent.busy ? "Ferma" : "Parla"
                tint: "white"
                fill: parent.busy ? "#d9364b" : (face.s.dark ? "#3a404a" : "#1f242b")
                onClicked: face.s.send(parent.busy ? "stop" : "listen")
            }
            TextField {
                id: input
                Layout.fillWidth: true
                placeholderText: "Chiedi qualcosa o dai un comando…"
                color: face.s.ink; placeholderTextColor: face.s.inkSoft
                font { family: face.s.sansFamily; pixelSize: 17 }
                background: Item {}
                onAccepted: { if (text.trim()) face.s.send("text", { text: text }); text = "" }
            }
            IconButton {
                size: 44; glyph: "send"; tip: "Invia"
                tint: input.text ? "#0b1015" : face.s.inkSoft
                fill: input.text ? face.s.led : "transparent"
                onClicked: input.accepted()
            }
        }
    }

    Loader {
        anchors.fill: parent
        active: face.s.editorOpen
        z: 10
        sourceComponent: Editor { store: face.s }
    }

    SettingsPanel {
        store: face.s
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom; margins: 24; topMargin: 90 }
        width: 380
        x: face.s.settingsOpen ? face.width - width - 24 : face.width + 20
        visible: face.s.settingsOpen
    }
}
