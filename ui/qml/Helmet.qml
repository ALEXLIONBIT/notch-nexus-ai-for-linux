import QtQuick
import QtQuick.Shapes
import QtQuick.Effects

// Il casco del robot: forma, orecchie, antenne e accessori cambiano con le preferenze e il tema.
Item {
    id: helmet
    required property var store
    readonly property var s: store
    readonly property var th: s.th
    property bool animated: true

    // forma → proporzioni, raggio del guscio e del visore, griglia LED
    readonly property var shape: ({
        capsula: { aspect: 0.60, r: 0.44, vr: 0.42, m: 0.085, cols: 34, rows: 15 },
        tondo:   { aspect: 0.86, r: 0.50, vr: 0.50, m: 0.10,  cols: 26, rows: 15 },
        tv:      { aspect: 0.74, r: 0.12, vr: 0.07, m: 0.10,  cols: 30, rows: 17 },
        cubo:    { aspect: 0.86, r: 0.22, vr: 0.16, m: 0.10,  cols: 28, rows: 17 }
    })[s.helmetShape] || ({ aspect: 0.6, r: 0.44, vr: 0.42, m: 0.085, cols: 34, rows: 15 })
    implicitHeight: width * shape.aspect
    height: width * shape.aspect

    property real bob: 0
    SequentialAnimation on bob { running: helmet.animated; loops: Animation.Infinite
        NumberAnimation { to: -6; duration: 2600; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: 2600; easing.type: Easing.InOutSine } }
    transform: Translate { y: helmet.bob }
    scale: s.st === "listening" && animated ? 1.025 : 1
    Behavior on scale { NumberAnimation { duration: 380; easing.type: Easing.OutBack } }

    // ---------- antenne ----------
    Repeater {
        model: helmet.s.antenna === "due" ? 2 : helmet.s.antenna === "una" ? 1 : 0
        Item {
            readonly property real len: helmet.height * 0.30
            width: helmet.height * 0.09; height: len
            x: (helmet.s.antenna === "una" ? helmet.width / 2 : helmet.width * (index === 0 ? 0.32 : 0.68)) - width / 2
            y: -len + helmet.height * 0.04
            rotation: helmet.s.antenna === "due" ? (index === 0 ? -22 : 22) : 0
            transformOrigin: Item.Bottom
            Rectangle {
                width: Math.max(4, helmet.height * 0.022); height: parent.height
                anchors.horizontalCenter: parent.horizontalCenter
                radius: width / 2; color: helmet.s.shellBot
            }
            Rectangle {
                width: parent.width; height: width; radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                color: helmet.s.stateColor
                layer.enabled: true
                layer.effect: MultiEffect { shadowEnabled: true; shadowColor: helmet.s.stateColor; shadowBlur: 1; blurMax: 24; shadowHorizontalOffset: 0; shadowVerticalOffset: 0 }
                SequentialAnimation on opacity { running: helmet.s.st === "listening"; loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 500 } NumberAnimation { to: 1; duration: 500 }
                    onRunningChanged: if (!running) parent.opacity = 1 }
            }
        }
    }

    // ---------- orecchie ----------
    Repeater {
        model: helmet.s.ears ? 2 : 0
        Rectangle {
            width: helmet.height * (helmet.s.helmetShape === "capsula" ? 0.30 : 0.22); height: width
            radius: helmet.s.helmetShape === "tv" || helmet.s.helmetShape === "cubo" ? width * 0.25 : width / 2
            x: index === 0 ? -width * 0.42 : helmet.width - width * 0.58
            y: helmet.height * 0.42 - height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: helmet.s.shellTop }
                GradientStop { position: 1; color: helmet.s.shellBot }
            }
            border.color: helmet.th.shellLine; border.width: helmet.th.shellLine === "#00000000" ? 0 : 1.5
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.52; height: width; radius: parent.radius * 0.52
                color: "transparent"; border.width: 3
                border.color: helmet.s.st === "idle" ? Qt.rgba(helmet.s.accentColor.r, helmet.s.accentColor.g, helmet.s.accentColor.b, 0.45) : helmet.s.stateColor
                Behavior on border.color { ColorAnimation { duration: 300 } }
            }
        }
    }

    // ---------- guscio ----------
    Rectangle {
        id: shell
        anchors.fill: parent
        radius: height * helmet.shape.r
        gradient: Gradient {
            GradientStop { position: 0.0; color: helmet.s.shellTop }
            GradientStop { position: 0.55; color: helmet.s.shellMid }
            GradientStop { position: 1.0; color: helmet.s.shellBot }
        }
        border.color: helmet.th.shellLine
        border.width: helmet.th.shellLine === "#00000000" ? 0 : 2
        layer.enabled: helmet.th.shadowOp > 0
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: helmet.th.shadow; shadowOpacity: helmet.th.shadowOp
            shadowBlur: 1; blurMax: 64; shadowVerticalOffset: 28; shadowHorizontalOffset: 0
        }
        // spicchi della zucca (Halloween)
        Repeater {
            model: helmet.th.deco === "halloween" ? 5 : 0
            Rectangle {
                width: shell.width * (0.95 - index * 0.19); height: shell.height
                anchors.centerIn: parent
                radius: Math.min(width, height) / 2
                color: "transparent"
                border.color: "#80501a00"; border.width: 3
                opacity: 0.55
            }
        }
    }

    // ---------- visore ----------
    Rectangle {
        id: visor
        anchors.fill: parent
        anchors.margins: parent.height * helmet.shape.m
        radius: height * helmet.shape.vr
        color: helmet.th.glass
        border.color: "#000000"; border.width: 2
        DotFace {
            store: helmet.s
            cols: helmet.shape.cols; rows: helmet.shape.rows
            width: Math.min(parent.width * 0.86, parent.height * 0.8 * cols / rows)
            height: width * rows / cols
            anchors.centerIn: parent
        }
        Shape {   // riflesso del vetro
            anchors.fill: parent
            opacity: helmet.s.theme === "oled" ? 0.06 : 0.16
            ShapePath {
                strokeWidth: -1
                fillGradient: LinearGradient {
                    x1: 0; y1: 0; x2: visor.width * 0.4; y2: visor.height * 0.5
                    GradientStop { position: 0; color: "white" }
                    GradientStop { position: 1; color: "transparent" }
                }
                startX: Math.max(visor.radius * 0.5, visor.width * 0.04); startY: visor.height * 0.06
                PathLine { x: visor.width * 0.55; y: visor.height * 0.06 }
                PathLine { x: visor.width * 0.18; y: visor.height * 0.62 }
                PathQuad { x: Math.max(visor.radius * 0.5, visor.width * 0.04); y: visor.height * 0.06; controlX: visor.width * 0.02; controlY: visor.height * 0.2 }
            }
        }
    }

    // ---------- accessori dei temi ----------
    // cappello di Babbo Natale
    Item {
        id: hat
        visible: helmet.th.deco === "natale"
        width: helmet.width * 0.36; height: width * 0.78
        x: helmet.width * 0.56; y: -height * 0.58
        rotation: 16
        Shape {
            anchors.fill: parent
            ShapePath {
                strokeWidth: -1
                fillGradient: LinearGradient { x1: 0; y1: 0; x2: 0; y2: hat.height
                    GradientStop { position: 0; color: "#e8363f" } GradientStop { position: 1; color: "#a5121b" } }
                startX: hat.width * 0.04; startY: hat.height * 0.86
                PathQuad { x: hat.width * 0.86; y: hat.height * 0.14; controlX: hat.width * 0.28; controlY: hat.height * 0.0 }
                PathQuad { x: hat.width * 0.96; y: hat.height * 0.86; controlX: hat.width * 0.72; controlY: hat.height * 0.45 }
                PathLine { x: hat.width * 0.04; y: hat.height * 0.86 }
            }
        }
        Rectangle {   // bordo di pelliccia
            width: hat.width * 1.04; height: hat.height * 0.22; radius: height / 2
            x: -hat.width * 0.02; y: hat.height * 0.76; color: "#fbf8f2"
        }
        Rectangle {   // pon pon
            width: hat.width * 0.2; height: width; radius: width / 2
            x: hat.width * 0.78; y: hat.height * 0.04; color: "#fbf8f2"
        }
    }
    // picciolo della zucca
    Rectangle {
        visible: helmet.th.deco === "halloween"
        width: helmet.width * 0.07; height: helmet.height * 0.2
        x: helmet.width * 0.5 - width / 2; y: -height * 0.8
        radius: width * 0.35; rotation: 10
        gradient: Gradient { GradientStop { position: 0; color: "#5e7d2e" } GradientStop { position: 1; color: "#2f4417" } }
    }
}
