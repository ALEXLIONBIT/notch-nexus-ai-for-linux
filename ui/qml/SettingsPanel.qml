import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

// Pannello "Personalizza": tema, colori, forma, occhi, bocca, editor di disegno, voce.
Rectangle {
    id: panel
    required property var store
    readonly property var s: store
    readonly property var cfg: s.config
    radius: 26
    color: s.dark ? "#1f2328" : "#ffffff"
    layer.enabled: true
    layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#000000"; shadowOpacity: 0.35; shadowBlur: 1; blurMax: 48; shadowVerticalOffset: 12; shadowHorizontalOffset: 0 }

    function sendCfg(k, v) { var o = {}; o[k] = v; s.send("config", { config: o }) }
    readonly property color chip: s.dark ? "#2a2f36" : "#eef1f4"
    readonly property color chipOn: s.dark ? "#444b55" : "#ffffff"

    // quale colore si sta modificando: "led" | "accent" | "shell" | "bg"
    property string editing: ""

    component Heading: Text {
        color: panel.s.inkSoft
        font { family: panel.s.sansFamily; pixelSize: 13; weight: Font.DemiBold }
        Layout.topMargin: 8
    }
    component Section: Text {
        color: panel.s.ink
        font { family: panel.s.sansFamily; pixelSize: 18; weight: Font.ExtraBold }
        Layout.topMargin: 18
    }
    component Chips: Flow {
        id: chips
        property var options: []
        property var labels: options
        property string current: ""
        signal picked(string v)
        Layout.preferredWidth: col.width; Layout.maximumWidth: col.width
        spacing: 8
        Repeater {
            model: chips.options
            Rectangle {
                width: lbl.implicitWidth + 28; height: 36; radius: 18
                color: chips.current === modelData ? panel.s.ink : panel.chip
                Behavior on color { ColorAnimation { duration: 120 } }
                Text {
                    id: lbl; anchors.centerIn: parent; text: chips.labels[index] || ""
                    color: chips.current === modelData ? (panel.s.dark ? "#16181c" : "#ffffff") : panel.s.ink
                    font { family: panel.s.sansFamily; pixelSize: 13; weight: Font.DemiBold }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: chips.picked(modelData) }
            }
        }
    }
    component ColorRow: RowLayout {
        id: cr
        property string label
        property string hint: ""
        property color value
        property bool custom: true
        property string key
        Layout.fillWidth: true
        spacing: 12
        Rectangle {
            width: 40; height: 40; radius: 20
            color: cr.value
            border.color: panel.s.inkSoft; border.width: 1
            Rectangle { visible: !cr.custom; anchors.centerIn: parent; width: 12; height: 12; radius: 6; color: "transparent"; border.color: panel.s.ink; border.width: 2 }
        }
        ColumnLayout {
            spacing: 0; Layout.fillWidth: true; Layout.preferredWidth: 1
            Text { text: cr.label; color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 14; weight: Font.Bold } }
            Text { text: cr.custom ? cr.value.toString().toUpperCase() : cr.hint; color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 12 }
                   Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
        IconButton { text: "Cambia"; size: 32; tint: panel.s.ink; fill: panel.chip
            onClicked: { panel.editing = cr.key; picker.title = cr.label; picker.allowReset = cr.key !== "led"; picker.load(cr.value) } }
    }
    component Dial: ColumnLayout {
        id: dial
        property string label
        property real from: 0
        property real to: 1
        property real value: 0
        property string shown: ""
        signal moved(real v)
        signal committed(real v)
        Layout.fillWidth: true
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            Heading { text: dial.label; Layout.fillWidth: true; Layout.topMargin: 0 }
            Text { text: dial.shown; color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 13; weight: Font.Bold } }
        }
        Slider {
            id: sl
            Layout.fillWidth: true
            from: dial.from; to: dial.to; value: dial.value
            onMoved: { dial.value = value; dial.moved(value) }
            onPressedChanged: if (!pressed) dial.committed(value)
            background: Rectangle {
                x: sl.leftPadding; y: sl.topPadding + sl.availableHeight / 2 - 3
                width: sl.availableWidth; height: 6; radius: 3; color: panel.chip
                Rectangle { width: sl.visualPosition * parent.width; height: 6; radius: 3; color: panel.s.ink }
            }
            handle: Rectangle {
                x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
                y: sl.topPadding + sl.availableHeight / 2 - height / 2
                width: 22; height: 22; radius: 11; color: panel.chipOn
                border.color: panel.s.ink; border.width: 2
            }
        }
    }

    Flickable {
        id: flick
        anchors.fill: parent; anchors.margins: 26
        contentHeight: col.implicitHeight + 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        ColumnLayout {
            id: col
            width: flick.width - 6
            spacing: 10

            Text { text: "Personalizza"; color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 26; weight: Font.ExtraBold } }

            // anteprima dal vivo del robot intero
            Rectangle {
                Layout.preferredWidth: col.width; Layout.preferredHeight: 200
                radius: 22; color: panel.s.bg; clip: true
                border.color: panel.s.dark ? "#2f343c" : "#e3e7eb"
                Helmet {
                    store: panel.s; animated: false
                    width: parent.width * (shape.aspect > 0.7 ? 0.46 : 0.58)
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: panel.s.antenna !== "nessuna" || panel.s.th.deco !== "" ? 14 : 0
                }
            }

            // ---------- tema ----------
            Section { text: "Tema" }
            GridLayout {
                Layout.fillWidth: true
                columns: 3; rowSpacing: 10; columnSpacing: 10
                Repeater {
                    model: ["perla", "grafite", "oled", "natale", "halloween", "plasma"]
                    Rectangle {
                        id: themeCard
                        readonly property string key: modelData
                        readonly property var t: panel.s.themes[modelData]
                        Layout.preferredWidth: (col.width - 20) / 3; Layout.preferredHeight: 84
                        radius: 16; color: t.bg
                        border.width: panel.s.theme === modelData ? 3 : 1
                        border.color: panel.s.theme === modelData ? panel.s.ink : (panel.s.dark ? "#3a3f48" : "#d8dde2")
                        Rectangle {     // mini casco
                            width: parent.width * 0.56; height: width * 0.48; radius: height * 0.44
                            anchors.horizontalCenter: parent.horizontalCenter; y: 12
                            color: t.shellMid; border.color: t.shellLine; border.width: t.shellLine === "#00000000" ? 0 : 1
                            Rectangle {
                                anchors.fill: parent; anchors.margins: 4; radius: height * 0.42; color: t.glass
                                Row { anchors.centerIn: parent; spacing: 7
                                    Repeater { model: 2; Rectangle { width: 7; height: 7; radius: themeCard.key === "halloween" ? 1 : 3.5; color: themeCard.t.led } } }
                            }
                        }
                        Text {
                            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 9 }
                            text: t.name; color: t.ink
                            font { family: panel.s.sansFamily; pixelSize: 12; weight: Font.Bold }
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: panel.s.applyTheme(modelData) }
                    }
                }
            }

            // ---------- colori ----------
            Section { text: "Colori" }
            ColorRow { label: "Principale"; key: "led"; value: panel.s.led }
            Flow {
                Layout.preferredWidth: col.width; Layout.maximumWidth: col.width; spacing: 8
                Repeater {
                    model: ["#9be7ff", "#f4f7fa", "#8cf5c8", "#ff9fd8", "#ffc861", "#b9a6ff", "#ff5a6e", "#3daee9", "#7dff6b", "#ff8a3d"]
                    Rectangle {
                        width: 28; height: 28; radius: 14; color: modelData
                        border.width: Qt.colorEqual(panel.s.led, modelData) ? 3 : 0; border.color: panel.s.ink
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: panel.s.led = modelData }
                    }
                }
            }
            ColorRow { label: "Secondario"; key: "accent"; hint: "Come il principale (bocca, antenne, orecchie)"
                       value: panel.s.accentColor; custom: panel.s.accent.a > 0 }
            ColorRow { label: "Guscio"; key: "shell"; hint: "Quello del tema"; value: panel.s.shellMid; custom: panel.s.hasShell }
            ColorRow { label: "Sfondo"; key: "bg"; hint: "Quello del tema"; value: panel.s.bg; custom: panel.s.hasBg }

            // ---------- faccia ----------
            Section { text: "Faccia" }
            IconButton {
                Layout.fillWidth: true
                text: "Disegna il tuo robot"; size: 46
                tint: "#0b1015"; fill: panel.s.led
                onClicked: panel.s.editorOpen = true
            }
            Heading { text: "Occhi" }
            Chips {
                options: ["tondi", "quadrati", "linee", "triangoli", "cuori", "disegnati"]
                labels: ["Tondi", "Quadrati", "Linee", "Triangoli", "Cuori", "Disegnati da te"]
                current: panel.s.eyeStyle; onPicked: v => panel.s.eyeStyle = v
            }
            Heading { text: "Bocca" }
            Chips {
                options: ["sorriso", "linea", "o", "zigzag", "disegnata"]
                labels: ["Sorriso", "Linea", "Tonda", "Zig zag", "Disegnata da te"]
                current: panel.s.mouthStyle; onPicked: v => panel.s.mouthStyle = v
            }
            Heading { text: "LED" }
            Chips { options: ["tondi", "quadrati"]; labels: ["Tondi", "Quadrati (pixel)"]; current: panel.s.dotShape; onPicked: v => panel.s.dotShape = v }
            Dial { label: "Bagliore"; from: 0; to: 1; value: panel.s.glowAmount; shown: Math.round(value * 100) + "%"
                   onMoved: v => panel.s.glowAmount = v }

            // ---------- corpo ----------
            Section { text: "Corpo" }
            Heading { text: "Forma del casco" }
            Chips { options: ["capsula", "tondo", "tv", "cubo"]; labels: ["Capsula", "Tondo", "TV", "Cubo"]
                    current: panel.s.helmetShape; onPicked: v => panel.s.helmetShape = v }
            Heading { text: "Antenna" }
            Chips { options: ["nessuna", "una", "due"]; labels: ["Nessuna", "Una", "Due"]
                    current: panel.s.antenna; onPicked: v => panel.s.antenna = v }
            Heading { text: "Orecchie" }
            Chips { options: ["si", "no"]; labels: ["Sì", "No"]; current: panel.s.ears ? "si" : "no"; onPicked: v => panel.s.ears = (v === "si") }

            // ---------- browser ----------
            Section { text: "Browser" }
            Heading { text: "Dove apre siti e ricerche"; Layout.topMargin: 0 }
            Chips {
                options: [""].concat(panel.s.browsers.map(b => b.id))
                labels: ["Predefinito di sistema"].concat(panel.s.browsers.map(b => b.name))
                current: panel.cfg.browser || ""
                onPicked: v => panel.sendCfg("browser", v)
            }

            // ---------- voce ----------
            Section { text: "Voce" }
            Chips {
                options: ["it_IT-paola-medium", "it_IT-riccardo-x_low"]; labels: ["Paola", "Riccardo"]
                current: panel.cfg.voice || ""; onPicked: v => panel.sendCfg("voice", v)
            }
            Dial { label: "Effetto robot"; from: 0; to: 1; value: panel.cfg.robot_strength ?? 0.45
                   shown: Math.round(value * 100) + "%"; onCommitted: v => panel.sendCfg("robot_strength", v) }
            Dial { label: "Velocità"; from: 0.7; to: 1.6; value: panel.cfg.voice_speed ?? 1.0
                   shown: value.toFixed(2) + "×"; onCommitted: v => panel.sendCfg("voice_speed", v) }

            // ---------- ascolto ----------
            Section { text: "Ascolto" }
            Heading { text: "Parola per svegliarlo" }
            Chips {
                options: ["hey_jarvis", "alexa", "hey_mycroft"]; labels: ["Hey Jarvis", "Alexa", "Hey Mycroft"]
                current: panel.cfg.wake_word || ""; onPicked: v => panel.sendCfg("wake_word", v)
            }
            Chips {
                options: ["on", "off"]; labels: ["Ascolto sempre attivo", "Solo col pulsante"]
                current: (panel.cfg.wake_enabled ?? true) ? "on" : "off"
                onPicked: v => panel.sendCfg("wake_enabled", v === "on")
            }
            Heading { text: "Cervello (modello Ollama)" }
            TextField {
                Layout.fillWidth: true; text: panel.cfg.model || ""
                color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 14 }
                leftPadding: 14
                background: Rectangle { implicitHeight: 40; radius: 20; color: panel.chip }
                onEditingFinished: if (text.trim()) panel.sendCfg("model", text.trim())
            }
        }
    }

    ColorPicker {
        id: picker
        store: panel.s
        visible: panel.editing !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        y: 90
        width: parent.width - 40
        onPicked: c => {
            if (panel.editing === "led") panel.s.led = c
            else if (panel.editing === "accent") panel.s.accent = c
            else if (panel.editing === "shell") panel.s.shellCustom = c
            else if (panel.editing === "bg") panel.s.bgCustom = c
        }
        onReset: {
            if (panel.editing === "accent") panel.s.accent = "#00000000"
            else if (panel.editing === "shell") panel.s.shellCustom = "#00000000"
            else if (panel.editing === "bg") panel.s.bgCustom = "#00000000"
            panel.editing = ""
        }
        onClosed: panel.editing = ""
    }
}
