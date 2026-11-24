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
    property bool providerOpen: false

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

            // ---------- modalità ----------
            Section { text: "Modalità" }
            Chips {
                options: ["manuale", "auto"]; labels: ["Manuale: chiede conferma", "⚡ Auto: fa tutto da solo"]
                current: panel.cfg.auto_mode ? "auto" : "manuale"
                onPicked: v => panel.sendCfg("auto_mode", v === "auto")
            }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                text: "Puoi anche dire “mettiti in automode” o “torna in manuale”. In Auto i comandi distruttivi (formattare dischi, cancellare il sistema) restano comunque bloccati."
                color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 11 }
            }

            // ---------- ascolto ----------
            Section { text: "Ascolto" }
            Heading { text: "Come si chiama" }
            TextField {
                id: agentName
                Layout.preferredWidth: col.width
                text: panel.cfg.agent_name || "Nexus"
                placeholderText: "Il nome del tuo assistente (es. Marco, Jarvis, Robo)"
                color: panel.s.ink; placeholderTextColor: panel.s.inkSoft
                font { family: panel.s.sansFamily; pixelSize: 13 }
                leftPadding: 14; maximumLength: 30
                background: Rectangle { implicitHeight: 38; radius: 19; color: panel.chip }
                onEditingFinished: if (text.trim() && text.trim() !== panel.cfg.agent_name) panel.sendCfg("agent_name", text.trim())
            }
            Heading { text: "Parola per svegliarlo" }
            Chips {
                options: ["name", "hey_jarvis", "alexa", "hey_mycroft"]
                labels: ["Ehi " + (panel.cfg.agent_name || "Nexus"), "Hey Jarvis", "Alexa", "Hey Mycroft"]
                current: panel.cfg.wake_word || ""; onPicked: v => panel.sendCfg("wake_word", v)
            }
            Text {
                visible: panel.cfg.wake_word === "name"
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                text: "Chiamalo per nome: “Ehi " + (panel.cfg.agent_name || "Nexus") + "” oppure tutto di fila, “"
                      + (panel.cfg.agent_name || "Nexus") + ", che tempo fa domani?”. La prima volta scarica un piccolo modello (75 MB)."
                color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 11 }
            }
            Chips {
                options: ["on", "off"]; labels: ["Ascolto sempre attivo", "Solo col pulsante"]
                current: (panel.cfg.wake_enabled ?? true) ? "on" : "off"
                onPicked: v => panel.sendCfg("wake_enabled", v === "on")
            }
            // ---------- cervello ----------
            Section { text: "Cervello" }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                text: "Dove gira l'intelligenza. Puoi usare questo PC, un PC più potente in casa o via Tailscale, oppure un servizio online con chiave API."
                color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 12 }
            }
            Repeater {
                model: panel.cfg.providers || []
                Rectangle {
                    readonly property bool active: panel.cfg.provider === modelData.id
                    Layout.preferredWidth: col.width; Layout.preferredHeight: 62
                    radius: 16
                    color: active ? (panel.s.dark ? "#2f353e" : "#f2f6f9") : "transparent"
                    border.width: active ? 2 : 1
                    border.color: active ? panel.s.ink : (panel.s.dark ? "#33383f" : "#e3e7eb")
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: panel.sendCfg("provider", modelData.id) }
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 8; spacing: 10
                        Rectangle { width: 14; height: 14; radius: 7; color: "transparent"; border.width: 2; border.color: panel.s.ink
                            Rectangle { visible: parent.parent.parent.active; anchors.centerIn: parent; width: 6; height: 6; radius: 3; color: panel.s.ink } }
                        ColumnLayout {
                            spacing: 1; Layout.fillWidth: true; Layout.preferredWidth: 1
                            Text { text: modelData.name; color: panel.s.ink; elide: Text.ElideRight; Layout.fillWidth: true
                                   font { family: panel.s.sansFamily; pixelSize: 14; weight: Font.Bold } }
                            Text { text: (modelData.model || "—") + "  ·  " + modelData.base_url.replace(/^https?:\/\//, "")
                                   color: panel.s.inkSoft; elide: Text.ElideRight; Layout.fillWidth: true
                                   font { family: panel.s.sansFamily; pixelSize: 11 } }
                        }
                        IconButton { text: "Modifica"; size: 30; tint: panel.s.ink; fill: panel.chip
                            onClicked: { editor.open(modelData); panel.providerOpen = true } }
                        IconButton { glyph: "close"; size: 30; tint: panel.s.inkSoft; tip: "Elimina"
                            visible: (panel.cfg.providers || []).length > 1
                            onClicked: panel.s.send("provider_delete", { id: modelData.id }) }
                    }
                }
            }
            IconButton {
                Layout.preferredWidth: col.width
                text: "+ Aggiungi provider"; size: 40; tint: panel.s.ink; fill: panel.chip
                onClicked: { editor.open(null); panel.providerOpen = true }
            }

            // ---------- modelli ----------
            Section { text: "Modelli" }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                color: panel.s.models.error ? "#ff5a6e" : panel.s.inkSoft
                font { family: panel.s.sansFamily; pixelSize: 12 }
                Component.onCompleted: panel.s.send("models_installed")
                text: panel.s.models.error ? "Errore: " + panel.s.models.error
                    : "Cerca, scarica e cambia il cervello su " + (panel.s.models.target || "Ollama")
                      + (panel.s.vramGb > 0 ? " · scheda video " + panel.s.vramGb + " GB" : "")
            }
            Repeater {
                model: panel.s.models.installed || []
                RowLayout {
                    readonly property bool inUse: modelData.name === panel.s.models.current
                    Layout.preferredWidth: col.width; spacing: 8
                    Text { text: (parent.inUse ? "● " : "") + modelData.name; color: panel.s.ink; elide: Text.ElideRight
                           Layout.fillWidth: true; font { family: panel.s.sansFamily; pixelSize: 13; weight: parent.inUse ? Font.Bold : Font.Normal } }
                    Text { text: modelData.size_gb + " GB"; color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 11 } }
                    IconButton { visible: !parent.inUse; text: "Usa"; size: 28; tint: panel.s.ink; fill: panel.chip
                        onClicked: panel.s.send("model_use", { name: modelData.name }) }
                    IconButton { visible: !parent.inUse; glyph: "close"; size: 28; tint: panel.s.inkSoft; tip: "Elimina"
                        onClicked: panel.s.send("model_delete", { name: modelData.name }) }
                }
            }
            TextField {
                id: modelQuery
                Layout.preferredWidth: col.width
                placeholderText: "Cerca un modello (qwen, gemma, llama, mistral…)"
                color: panel.s.ink; placeholderTextColor: panel.s.inkSoft
                font { family: panel.s.sansFamily; pixelSize: 13 }
                leftPadding: 14
                background: Rectangle { implicitHeight: 38; radius: 19; color: panel.chip }
                onAccepted: { panel.s.modelSearching = true; panel.s.send("models_search", { query: text.trim() }) }
            }
            Text {
                visible: panel.s.modelSearching || (panel.s.modelProgress.text !== "" && !panel.s.modelProgress.done) || panel.s.modelProgress.error !== ""
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                color: panel.s.modelProgress.error ? "#ff5a6e" : panel.s.ink
                font { family: panel.s.sansFamily; pixelSize: 12 }
                text: panel.s.modelProgress.error ? "Non installato: " + panel.s.modelProgress.error
                    : panel.s.modelSearching ? "Cerco…" : panel.s.modelProgress.text
            }
            Rectangle {
                visible: !panel.s.modelProgress.done && panel.s.modelProgress.pct >= 0
                Layout.preferredWidth: col.width; height: 6; radius: 3; color: panel.chip
                Rectangle { width: parent.width * Math.max(0, panel.s.modelProgress.pct) / 100; height: parent.height; radius: 3; color: panel.s.led }
            }
            Repeater {
                model: panel.s.modelResults
                ColumnLayout {
                    Layout.preferredWidth: col.width; spacing: 4
                    Text { text: modelData.name + (modelData.caps.length ? "   " + modelData.caps.join(" · ") : "")
                           color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 13; weight: Font.Bold } }
                    Text { text: modelData.desc; color: panel.s.inkSoft; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                           Layout.preferredWidth: col.width; font { family: panel.s.sansFamily; pixelSize: 11 } }
                    Flow {
                        Layout.preferredWidth: col.width; spacing: 6
                        Repeater {
                            model: modelData.sizes.length ? modelData.sizes : [{ tag: "latest", gb: null, fit: "" }]
                            IconButton {
                                readonly property string full: parent.parent.modelName + ":" + modelData.tag
                                text: modelData.tag + (modelData.gb ? " · " + modelData.gb + " GB" : "")
                                tip: modelData.fit === "gpu" ? "Entra nella scheda video: veloce"
                                   : modelData.fit === "cpu" ? "Non entra nella scheda video: va, ma lento"
                                   : modelData.fit === "big" ? "Troppo grande per questo PC" : "Scarica e usa"
                                size: 28; tint: modelData.fit === "gpu" ? "#0b1015" : panel.s.ink
                                fill: modelData.fit === "gpu" ? panel.s.led : modelData.fit === "big" ? (panel.s.dark ? "#4a2a30" : "#f6dde1") : panel.chip
                                enabled: panel.s.modelProgress.done
                                onClicked: panel.s.send("model_pull", { name: full, use: true })
                            }
                        }
                    }
                    readonly property string modelName: modelData.name
                }
            }

            // ---------- tailscale ----------
            Section { text: "Tailscale" }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                color: panel.s.tailscale.error ? "#ff5a6e" : panel.s.inkSoft
                font { family: panel.s.sansFamily; pixelSize: 12 }
                Component.onCompleted: panel.s.send("tailscale_status")
                text: panel.s.tailscale.error ? "Errore: " + panel.s.tailscale.error
                    : panel.s.tailscale.text ? panel.s.tailscale.text
                    : !panel.s.tailscale.installed ? "Tailscale non è installato: collega telefono, orologio e altri PC al tuo NEXUS anche fuori casa."
                    : panel.s.tailscale.state === "Running" ? "Collegato come " + panel.s.tailscale.name + " (" + panel.s.tailscale.ip + ")"
                    : "Tailscale è installato ma non collegato."
            }
            RowLayout {
                spacing: 8
                IconButton { visible: panel.s.tailscale.state !== "Running"; enabled: !panel.s.tailscale.working
                    text: panel.s.tailscale.working ? "Mi collego…" : "Collega Tailscale"; size: 34; tint: "#0b1015"; fill: panel.s.led
                    onClicked: panel.s.send("tailscale_connect") }
                IconButton { text: "Aggiorna stato"; size: 34; tint: panel.s.ink; fill: panel.chip; onClicked: panel.s.send("tailscale_status") }
            }

            // ---------- aggiornamenti ----------
            Section { text: "Aggiornamenti" }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                color: panel.s.update.error ? "#ff5a6e" : panel.s.inkSoft
                font { family: panel.s.sansFamily; pixelSize: 12 }
                text: panel.s.update.restarting ? "Riavvio NEXUS…"
                    : panel.s.update.working ? "Scarico l'aggiornamento…"
                    : panel.s.update.error ? "Non riesco a controllare: " + panel.s.update.error
                    : (panel.s.update.current ? "Versione: " + panel.s.update.current : "Controllo…")
                      + (panel.s.update.behind > 0 ? "\n" + panel.s.update.behind + " novità disponibili:\n" + panel.s.update.news.join("\n")
                                                   : (panel.s.update.current ? "\nÈ l'ultima versione." : ""))
            }
            RowLayout {
                spacing: 8
                IconButton { text: "Controlla"; size: 34; tint: panel.s.ink; fill: panel.chip; onClicked: panel.s.send("update_check") }
                IconButton { text: "Riavvia"; size: 34; tint: panel.s.ink; fill: panel.chip; tip: "Chiude e riapre tutto NEXUS"
                    onClicked: panel.s.send("restart") }
                IconButton { visible: panel.s.update.behind > 0; text: "Aggiorna ora"; size: 34; tint: "#0b1015"; fill: panel.s.led
                    onClicked: panel.s.send("update_apply") }
            }

            // ---------- trascrizione ----------
            Section { text: "Trascrizione" }
            Chips {
                options: ["turbo", "small", "remote"]
                labels: ["Su questo PC, precisa", "Su questo PC, leggera", "Online (API)"]
                current: panel.cfg.stt_mode === "remote" ? "remote" : (panel.cfg.stt_model === "small" ? "small" : "turbo")
                onPicked: v => {
                    if (v === "remote") panel.s.send("config", { config: { stt_mode: "remote" } })
                    else panel.s.send("config", { config: { stt_mode: "local", stt_model: v === "small" ? "small" : "large-v3-turbo" } })
                }
            }
            Text {
                visible: panel.cfg.stt_mode === "remote"
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap
                text: "Usa il provider scelto qui sotto (OpenAI o Groq). Per Groq il modello è whisper-large-v3-turbo."
                color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 12 }
            }
            Chips {
                visible: panel.cfg.stt_mode === "remote"
                options: (panel.cfg.providers || []).filter(p => p.kind !== "ollama").map(p => p.id)
                labels: (panel.cfg.providers || []).filter(p => p.kind !== "ollama").map(p => p.name)
                current: panel.cfg.stt_provider || ""
                onPicked: v => panel.sendCfg("stt_provider", v)
            }
            TextField {
                visible: panel.cfg.stt_mode === "remote"
                Layout.preferredWidth: col.width; text: panel.cfg.stt_remote_model || "whisper-1"
                color: panel.s.ink; font { family: panel.s.sansFamily; pixelSize: 13 }
                leftPadding: 14
                background: Rectangle { implicitHeight: 38; radius: 19; color: panel.chip }
                onEditingFinished: if (text.trim()) panel.sendCfg("stt_remote_model", text.trim())
            }

            // ---------- esci ----------
            IconButton {
                Layout.preferredWidth: col.width; Layout.topMargin: 24
                text: "Esci da NEXUS"; size: 42; tint: "white"; fill: "#d9364b"
                onClicked: nexus.quit()
            }
            Text {
                Layout.preferredWidth: col.width; wrapMode: Text.Wrap; Layout.bottomMargin: 10
                text: "Chiude il notch. Il backend resta acceso: per riaprire lancia “nexus” o riavvia il PC."
                color: panel.s.inkSoft; font { family: panel.s.sansFamily; pixelSize: 11 }
            }
        }
    }

    // velo + modulo provider
    Rectangle {
        anchors.fill: parent; radius: panel.radius
        color: Qt.rgba(0, 0, 0, 0.35); visible: panel.providerOpen
        MouseArea { anchors.fill: parent; onClicked: panel.providerOpen = false }
    }
    ProviderEditor {
        id: editor
        store: panel.s
        visible: panel.providerOpen
        anchors.horizontalCenter: parent.horizontalCenter
        y: 40
        width: parent.width - 28
        onClosed: panel.providerOpen = false
        Timer { running: panel.s.providerEditorRequest; interval: 2500
            onTriggered: { editor.open(null); editor.pickPreset("groq"); panel.providerOpen = true } }
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
