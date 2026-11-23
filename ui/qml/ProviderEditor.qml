import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Modulo per aggiungere o modificare un provider del "cervello".
Rectangle {
    id: pe
    required property var store
    readonly property var s: store
    property var editing: null           // provider esistente (senza chiave) oppure null = nuovo
    signal closed()

    property string preset: "ollama"
    readonly property var pr: s.presets[preset] || ({ kind: "openai", needs_key: false, base_url: "", model: "", label: "" })
    readonly property color field: s.dark ? "#1c1f24" : "#eef1f4"

    function open(p) {
        editing = p
        preset = p ? (p.preset || "custom") : "ollama"
        nameF.text = p ? p.name : (s.presets.ollama ? s.presets.ollama.label : "")
        urlF.text = p ? p.base_url : (s.presets.ollama ? s.presets.ollama.base_url : "")
        keyF.text = ""
        modelF.text = p ? p.model : (s.presets.ollama ? s.presets.ollama.model : "")
        s.providerModels = []; s.providerMsg = ""
    }
    function pickPreset(k) {
        preset = k
        var p = s.presets[k]
        if (!p) return
        if (!editing) nameF.text = p.label
        urlF.text = p.base_url; modelF.text = p.model
        s.providerModels = []; s.providerMsg = ""
    }
    function draft() {
        return { id: editing ? editing.id : "", name: nameF.text.trim() || pr.label, preset: preset, kind: pr.kind,
                 base_url: urlF.text.trim(), api_key: keyF.text.trim(), model: modelF.text.trim() }
    }

    radius: 22
    color: s.dark ? "#262a31" : "#ffffff"
    border.color: s.dark ? "#3a3f48" : "#e3e7eb"
    implicitHeight: col.implicitHeight + 36
    MouseArea { anchors.fill: parent }

    component Label2: Text { color: pe.s.inkSoft; font { family: pe.s.sansFamily; pixelSize: 12; weight: Font.DemiBold } }
    component Field: TextField {
        Layout.fillWidth: true
        color: pe.s.ink; placeholderTextColor: pe.s.inkSoft
        font { family: pe.s.sansFamily; pixelSize: 13 }
        leftPadding: 12; rightPadding: 12
        background: Rectangle { implicitHeight: 36; radius: 12; color: pe.field }
    }

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Text { text: pe.editing ? "Modifica provider" : "Aggiungi provider"; color: pe.s.ink
                   font { family: pe.s.sansFamily; pixelSize: 17; weight: Font.Bold } Layout.fillWidth: true }
            IconButton { glyph: "close"; tint: pe.s.ink; size: 30; onClicked: pe.closed() }
        }

        Label2 { text: "Tipo" }
        Flow {
            Layout.fillWidth: true; Layout.preferredWidth: col.width; spacing: 6
            Repeater {
                model: ["ollama", "openai", "anthropic", "gemini", "groq", "openrouter", "lmstudio", "custom"].filter(k => pe.s.presets[k] !== undefined)
                Rectangle {
                    width: t.implicitWidth + 20; height: 30; radius: 15
                    color: pe.preset === modelData ? pe.s.ink : pe.field
                    Text { id: t; anchors.centerIn: parent
                        text: pe.s.presets[modelData].label.replace(" (questo PC, rete o Tailscale)", "").replace(" (compatibile OpenAI)", "")
                        color: pe.preset === modelData ? (pe.s.dark ? "#16181c" : "#ffffff") : pe.s.ink
                        font { family: pe.s.sansFamily; pixelSize: 12; weight: Font.DemiBold } }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: pe.pickPreset(modelData) }
                }
            }
        }
        Text {
            visible: pe.pr.kind === "ollama"
            Layout.fillWidth: true; wrapMode: Text.Wrap
            text: "Per un altro PC (in casa o via Tailscale): lì avvia Ollama con OLLAMA_HOST=0.0.0.0 e qui scrivi http://IP-DEL-PC:11434"
            color: pe.s.inkSoft; font { family: pe.s.sansFamily; pixelSize: 11 }
        }

        Label2 { text: "Nome" }
        Field { id: nameF; placeholderText: "Es. PC fisso in salotto" }
        Label2 { text: "Indirizzo (URL)" }
        Field { id: urlF; placeholderText: "http://100.64.0.2:11434" }
        Label2 { text: pe.editing && pe.editing.api_key_hint ? "Chiave API (salvata: " + pe.editing.api_key_hint + ", lascia vuoto per tenerla)" : "Chiave API"  }
        Field { id: keyF; echoMode: TextInput.Password
                placeholderText: pe.pr.needs_key ? "sk-…" : "Facoltativa (se il server la chiede)" }

        Label2 { text: "Modello" }
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            Field { id: modelF; placeholderText: "Es. qwen3.5:9b" }
            IconButton { text: "Carica modelli"; size: 36; tint: pe.s.ink; fill: pe.field
                onClicked: { pe.s.providerMsg = "Carico…"; pe.s.send("provider_models", { id: pe.editing ? pe.editing.id : "", provider: pe.draft() }) } }
        }
        // lista modelli trovati
        Rectangle {
            visible: pe.s.providerModels.length > 0
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(150, pe.s.providerModels.length * 28 + 8)
            radius: 12; color: pe.field; clip: true
            ListView {
                anchors.fill: parent; anchors.margins: 4
                model: pe.s.providerModels
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    width: ListView.view.width; height: 28; radius: 8
                    color: modelF.text === modelData ? (pe.s.dark ? "#3a404a" : "#ffffff") : "transparent"
                    Text { anchors.verticalCenter: parent.verticalCenter; x: 10; text: modelData; elide: Text.ElideRight
                           width: parent.width - 20; color: pe.s.ink; font { family: pe.s.sansFamily; pixelSize: 12 } }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: modelF.text = modelData }
                }
            }
        }

        Text {
            visible: pe.s.providerMsg !== ""
            text: pe.s.providerMsg; wrapMode: Text.Wrap; Layout.fillWidth: true
            color: pe.s.providerOk ? "#3fb27f" : "#ff5a6e"
            font { family: pe.s.sansFamily; pixelSize: 12; weight: Font.DemiBold }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 6; spacing: 8
            IconButton { text: "Prova"; size: 38; tint: pe.s.ink; fill: pe.field
                onClicked: { pe.s.providerMsg = "Provo la connessione…"; pe.s.send("provider_test", { id: pe.editing ? pe.editing.id : "", provider: pe.draft() }) } }
            Item { Layout.fillWidth: true }
            IconButton { text: "Salva e usa"; size: 38; tint: "#0b1015"; fill: pe.s.led
                onClicked: { pe.s.send("provider_save", { provider: pe.draft(), select: true }); pe.closed() } }
        }
    }
}
