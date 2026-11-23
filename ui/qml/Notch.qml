import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

// Il notch: vetro nero attaccato al bordo alto dello schermo, come quello del Mac.
// A riposo mostra solo il mini-volto LED; quando NEXUS lavora si allarga e mostra sottotitoli e passi.
Item {
    id: notch
    required property var store
    readonly property var s: store
    readonly property bool busy: (s.st !== "idle" && s.st !== "loading") || s.confirmText !== "" || s.saying
    property bool pinned: false
    readonly property bool expanded: hover.hovered || busy || pinned || input.activeFocus
                                     || (s.reply !== "" && replyHold.running)

    readonly property real pillW: expanded ? 640 : 190
    readonly property real pillH: expanded ? Math.min(460, body.implicitHeight + header.height + 34) : 36
    implicitWidth: 640 + 60
    implicitHeight: pillH + 40

    HoverHandler { id: hover }
    Timer { id: replyHold; interval: 6000 }
    Connections { target: notch.s; function onReplyChanged() { replyHold.restart() } }

    Item {
        id: pillBox
        width: notch.pillW; height: notch.pillH
        anchors.horizontalCenter: parent.horizontalCenter
        Behavior on width { SpringAnimation { spring: 4.5; damping: 0.42; epsilon: 0.5 } }
        Behavior on height { SpringAnimation { spring: 4.5; damping: 0.5; epsilon: 0.5 } }

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: "#000000"; shadowOpacity: 0.55
            shadowBlur: 0.8; blurMax: 32; shadowVerticalOffset: 6; shadowHorizontalOffset: 0
        }

        // vetro: angoli in alto dritti (attaccato allo schermo), in basso arrotondati
        Rectangle {
            id: glass
            anchors.fill: parent
            anchors.topMargin: -radius
            radius: notch.expanded ? 28 : 18
            color: notch.s.glass
            border.color: Qt.rgba(1, 1, 1, 0.07); border.width: 1
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#05070a" }
                GradientStop { position: 1.0; color: "#0c1016" }
            }
        }
        // filo di luce sul bordo inferiore, col colore dello stato
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: parent.width * (notch.busy ? 0.55 : 0.3); height: 2; radius: 1
            color: notch.s.stateColor
            opacity: notch.busy ? 0.9 : 0.35
            Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 250 } }
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: notch.s.stateColor; shadowBlur: 1; blurMax: 16; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
        }

        clip: true

        // ---------- testata ----------
        RowLayout {
            id: header
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.leftMargin: notch.expanded ? 22 : 14
            anchors.rightMargin: notch.expanded ? 14 : 14
            anchors.topMargin: notch.expanded ? 12 : 5
            height: notch.expanded ? 40 : 26
            spacing: 14

            DotFace {
                store: notch.s
                cols: 17; rows: 7; glow: notch.expanded
                Layout.preferredWidth: notch.expanded ? 74 : 56
                Layout.preferredHeight: Layout.preferredWidth * rows / cols
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                visible: notch.expanded
                text: notch.s.statusText
                color: notch.s.st === "idle" ? "#c9d1da" : notch.s.stateColor
                font { family: notch.s.sansFamily; pixelSize: 15; weight: Font.DemiBold }
                elide: Text.ElideRight
                Layout.fillWidth: true
                Behavior on color { ColorAnimation { duration: 250 } }
            }
            Item { visible: !notch.expanded; Layout.fillWidth: true }

            Rectangle {   // spia: rossa pulsante quando ascolta
                visible: !notch.expanded || notch.s.st === "listening"
                width: 8; height: 8; radius: 4
                color: !notch.s.connected ? "#5b6470" : notch.s.st === "listening" ? notch.s.listenRed : notch.s.led
                opacity: notch.s.st === "listening" ? pulse.v : 0.75
                QtObject { id: pulse; property real v: 1
                    property var anim: SequentialAnimation { running: true; loops: Animation.Infinite
                        NumberAnimation { target: pulse; property: "v"; to: 0.25; duration: 600 }
                        NumberAnimation { target: pulse; property: "v"; to: 1; duration: 600 } } }
            }

            Row {
                visible: notch.expanded
                spacing: 2
                IconButton { glyph: "stop"; tip: "Ferma"; visible: notch.busy; tint: "white"; fill: "#d9364b"
                    onClicked: notch.s.send("stop") }
                IconButton { glyph: "mic"; tip: "Parla"; tint: "#e8edf2"; visible: !notch.busy; onClicked: notch.s.send("listen") }
                IconButton { glyph: notch.pinned ? "pinned" : "pin"; tip: notch.pinned ? "Lascia chiudere" : "Tieni aperto"; tint: "#e8edf2"; onClicked: notch.pinned = !notch.pinned }
                IconButton { glyph: "expand"; tip: "Schermo intero"; tint: "#e8edf2"; onClicked: notch.s.fullscreen = true }
            }
        }

        // ---------- corpo ----------
        ColumnLayout {
            id: body
            anchors { left: parent.left; right: parent.right; top: header.bottom }
            anchors.leftMargin: 24; anchors.rightMargin: 24; anchors.topMargin: 10
            spacing: 12
            opacity: notch.expanded ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 180 } }

            // quello che hai detto tu
            Text {
                visible: notch.s.transcript !== ""
                text: "Tu: " + notch.s.transcript
                color: "#7f8a96"; font { family: notch.s.sansFamily; pixelSize: 13 }
                wrapMode: Text.Wrap; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight
            }

            // sottotitoli in diretta (o l'ultima risposta)
            Subtitle {
                store: notch.s
                visible: notch.s.sayText !== ""
                litColor: "#ffffff"; dimColor: "#4d5763"
                font { family: notch.s.sansFamily; pixelSize: 19; weight: Font.DemiBold }
                lineHeight: 1.15
                Layout.fillWidth: true
            }
            Text {
                visible: notch.s.sayText === "" && notch.s.reply !== ""
                text: notch.s.reply
                color: "#e9eef3"; font { family: notch.s.sansFamily; pixelSize: 15 }
                wrapMode: Text.Wrap; Layout.fillWidth: true; maximumLineCount: 4; elide: Text.ElideRight
                lineHeight: 1.15
            }

            // passi + screenshot
            RowLayout {
                visible: notch.s.steps.count > 0
                Layout.fillWidth: true
                spacing: 14
                Column {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 6
                    Repeater {
                        model: notch.s.steps
                        Row {
                            spacing: 10
                            width: parent.width
                            readonly property bool current: index === notch.s.steps.count - 1
                            Rectangle {
                                width: 6; height: 6; radius: 3
                                anchors.verticalCenter: parent.verticalCenter
                                color: parent.current ? notch.s.stateColor : "#3a434e"
                            }
                            Text {
                                text: model.text
                                width: parent.width - 16
                                color: parent.current ? "#dfe6ec" : "#6e7984"
                                font { family: notch.s.sansFamily; pixelSize: 13 }
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
                Image {
                    visible: notch.s.image !== ""
                    source: notch.s.image
                    Layout.preferredWidth: 156; Layout.preferredHeight: 88
                    fillMode: Image.PreserveAspectCrop; cache: false
                    layer.enabled: true
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: thumbMask }
                    Rectangle { id: thumbMask; anchors.fill: parent; radius: 10; visible: false; layer.enabled: true }
                }
            }

            // conferma
            RowLayout {
                visible: notch.s.confirmText !== ""
                Layout.fillWidth: true
                spacing: 8
                Text {
                    text: notch.s.confirmText
                    color: notch.s.thinkAmber; font { family: notch.s.sansFamily; pixelSize: 14; weight: Font.DemiBold }
                    wrapMode: Text.Wrap; Layout.fillWidth: true
                }
                IconButton { text: "Sì, procedi"; tint: "#1a1306"; fill: notch.s.thinkAmber; size: 32
                    onClicked: notch.s.send("confirm", { id: notch.s.confirmId, ok: true }) }
                IconButton { text: "No"; tint: "#e8edf2"; fill: "#232a33"; size: 32
                    onClicked: notch.s.send("confirm", { id: notch.s.confirmId, ok: false }) }
            }

            // scrivi a NEXUS
            TextField {
                id: input
                Layout.fillWidth: true
                Layout.bottomMargin: 6
                placeholderText: "Scrivi a NEXUS…"
                color: "#eef2f5"; placeholderTextColor: "#56606b"
                font { family: notch.s.sansFamily; pixelSize: 14 }
                leftPadding: 16; rightPadding: 44
                background: Rectangle {
                    implicitHeight: 40; radius: 20
                    color: "#131920"
                    border.color: input.activeFocus ? Qt.rgba(notch.s.led.r, notch.s.led.g, notch.s.led.b, 0.6) : "#1e252e"
                }
                onAccepted: { if (text.trim()) notch.s.send("text", { text: text }); text = "" }
                IconButton {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 5 }
                    glyph: "send"; size: 30; tint: input.text ? "#0b1015" : "#56606b"
                    fill: input.text ? notch.s.led : "transparent"
                    onClicked: input.accepted()
                }
            }
        }
    }
}
