import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// Chat salvate: a sinistra l'elenco (cerca, nuova, elimina), a destra la conversazione con cui scrivere o parlare.
Window {
    id: win
    required property var store
    readonly property var s: store
    readonly property color bg: s.dark ? "#0f1318" : "#f6f8fa"
    readonly property color side: s.dark ? "#151a20" : "#ffffff"
    readonly property color line: s.dark ? "#242a32" : "#e3e7eb"
    readonly property color bubble: s.dark ? "#1d232b" : "#eef1f4"
    readonly property bool busy: s.st === "thinking" || s.st === "acting" || s.st === "speaking" || s.st === "listening"
    property var files: []          // allegati (Ctrl+V o trascinati sulla finestra)
    title: "NEXUS · Chat"
    width: 980; height: 680
    minimumWidth: 640; minimumHeight: 420
    color: bg
    visible: s.chatOpen
    onVisibleChanged: if (visible) { s.send("chats_list", { query: s.chatQuery }); input.forceActiveFocus() }
    onClosing: close => { close.accepted = false; s.chatOpen = false }

    function when(t) {
        var d = new Date(t * 1000), now = new Date()
        var hm = d.toLocaleTimeString(Qt.locale("it_IT"), "HH:mm")
        if (d.toDateString() === now.toDateString()) return hm
        var y = new Date(now); y.setDate(now.getDate() - 1)
        if (d.toDateString() === y.toDateString()) return "ieri " + hm
        return d.toLocaleDateString(Qt.locale("it_IT"), "d MMM") + " " + hm
    }

    DropArea {
        anchors.fill: parent
        onDropped: drop => { if (drop.hasUrls) { win.files = win.files.concat(clip.localFiles(drop.urls)); input.forceActiveFocus() } }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------------- elenco
        Rectangle {
            Layout.preferredWidth: 300; Layout.fillHeight: true
            color: win.side
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: win.line }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 14; spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Chat"; color: win.s.ink; Layout.fillWidth: true
                           font { family: win.s.sansFamily; pixelSize: 22; weight: Font.ExtraBold } }
                    IconButton { text: "+ Nuova"; size: 32; tint: "#0b1015"; fill: win.s.led
                        onClicked: { win.s.send("chat_new", { query: win.s.chatQuery }); input.forceActiveFocus() } }
                }
                TextField {
                    id: search
                    Layout.fillWidth: true
                    placeholderText: "Cerca nelle chat…"
                    text: win.s.chatQuery
                    color: win.s.ink; placeholderTextColor: win.s.inkSoft
                    font { family: win.s.sansFamily; pixelSize: 13 }
                    leftPadding: 34
                    background: Rectangle { implicitHeight: 36; radius: 18; color: win.bubble
                        Icon { name: "search"; color: win.s.inkSoft; width: 16; height: 16
                               anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter } } }
                    onTextChanged: { win.s.chatQuery = text; searchDelay.restart() }
                    Timer { id: searchDelay; interval: 250; onTriggered: win.s.send("chats_list", { query: search.text }) }
                }
                ListView {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; spacing: 4
                    model: win.s.chatList
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool current: modelData.id === win.s.chatId
                        width: ListView.view.width; height: 62; radius: 14
                        color: current ? win.bubble : (ma.containsMouse ? Qt.rgba(win.bubble.r, win.bubble.g, win.bubble.b, 0.5) : "transparent")
                        MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: win.s.send("chat_open", { id: modelData.id }) }
                        ColumnLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 36; topMargin: 8; bottomMargin: 8 }
                            spacing: 2
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: modelData.title; color: win.s.ink; elide: Text.ElideRight; Layout.fillWidth: true
                                       font { family: win.s.sansFamily; pixelSize: 13; weight: Font.Bold } }
                                Text { text: win.when(modelData.updated); color: win.s.inkSoft; font { family: win.s.sansFamily; pixelSize: 10 } }
                            }
                            Text { text: modelData.preview; color: win.s.inkSoft; elide: Text.ElideRight; Layout.fillWidth: true
                                   font { family: win.s.sansFamily; pixelSize: 11 } }
                        }
                        IconButton { glyph: "close"; size: 26; tint: win.s.inkSoft; tip: "Elimina"
                            anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            onClicked: win.s.send("chat_delete", { id: modelData.id, query: win.s.chatQuery }) }
                    }
                    Text {
                        anchors.centerIn: parent; width: parent.width - 20; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                        visible: parent.count === 0
                        text: win.s.chatQuery ? "Nessuna chat con “" + win.s.chatQuery + "”" : "Ancora nessuna chat: scrivi o parla a NEXUS."
                        color: win.s.inkSoft; font { family: win.s.sansFamily; pixelSize: 12 }
                    }
                }
            }
        }

        // ---------------------------------------------------------------- conversazione
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: 0
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 18; Layout.bottomMargin: 6
                Text {
                    Layout.fillWidth: true
                    text: win.s.chatTitle || "Nuova chat"; elide: Text.ElideRight
                    color: win.s.ink; font { family: win.s.sansFamily; pixelSize: 18; weight: Font.Bold }
                }
                IconButton { glyph: "close"; size: 32; tint: win.s.inkSoft; tip: "Chiudi"; onClicked: win.s.chatOpen = false }
            }
            ListView {
                id: msgs
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.leftMargin: 18; Layout.rightMargin: 18
                clip: true; spacing: 10
                model: win.s.chatMessages
                ScrollBar.vertical: ScrollBar {}
                onCountChanged: Qt.callLater(positionViewAtEnd)
                delegate: Item {
                    id: row
                    required property var modelData
                    readonly property bool mine: modelData.role === "user"
                    width: ListView.view.width
                    height: b.height
                    HoverHandler { id: rowHover }
                    IconButton {   // copia tutto il messaggio (per una parte: selezionala e Ctrl+C)
                        glyph: "copy"; size: 26; tint: win.s.inkSoft; tip: "Copia"
                        visible: rowHover.hovered
                        anchors.verticalCenter: b.verticalCenter
                        x: row.mine ? b.x - width - 4 : b.x + b.width + 4
                        onClicked: win.s.copy(row.modelData.text)
                    }
                    Rectangle {
                        id: b
                        anchors.right: row.mine ? row.right : undefined
                        width: Math.min(t.implicitWidth + 28, row.width * 0.78)
                        height: t.implicitHeight + 20
                        radius: 18
                        color: row.mine ? win.s.led : win.bubble
                        TextEdit {
                            id: t
                            x: 14; y: 10
                            width: Math.min(implicitWidth, row.width * 0.78 - 28)
                            text: row.modelData.text
                            readOnly: true; selectByMouse: true; wrapMode: Text.Wrap
                            selectionColor: row.mine ? "#ffffff" : Qt.rgba(win.s.led.r, win.s.led.g, win.s.led.b, 0.45)
                            selectedTextColor: "#0b1015"
                            color: row.mine ? "#0b1015" : win.s.ink
                            font { family: win.s.sansFamily; pixelSize: 14 }
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent; visible: parent.count === 0
                    text: "Scrivi qui sotto o premi il microfono per parlare."
                    color: win.s.inkSoft; font { family: win.s.sansFamily; pixelSize: 13 }
                }
            }
            Text {
                Layout.leftMargin: 20; Layout.topMargin: 4
                visible: win.s.toastText !== ""
                text: "✓ " + win.s.toastText
                color: win.s.ink; font { family: win.s.sansFamily; pixelSize: 12; weight: Font.Bold }
            }
            Attachments {
                Layout.fillWidth: true; Layout.leftMargin: 14; Layout.rightMargin: 14; Layout.topMargin: 6
                files: win.files; family: win.s.sansFamily
                ink: win.s.ink; chip: win.bubble
                onRemoved: i => { var f = win.files.slice(); f.splice(i, 1); win.files = f }
            }
            Text {
                Layout.leftMargin: 20; Layout.topMargin: 4
                visible: win.busy
                text: win.s.st === "listening" ? "Ti ascolto…" : win.s.st === "speaking" ? "Rispondo…" : (win.s.detail || "Ci penso…")
                color: win.s.inkSoft; font { family: win.s.sansFamily; pixelSize: 12; italic: true }
            }
            RowLayout {
                Layout.fillWidth: true; Layout.margins: 14; spacing: 8
                TextField {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: "Scrivi a NEXUS…"
                    color: win.s.ink; placeholderTextColor: win.s.inkSoft
                    font { family: win.s.sansFamily; pixelSize: 14 }
                    leftPadding: 16
                    background: Rectangle { implicitHeight: 44; radius: 22; color: win.bubble
                        border.color: input.activeFocus ? win.s.led : "transparent" }
                    Keys.onPressed: event => {
                        if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_V) {
                            var f = win.s.pasteFiles()
                            if (f.length) { win.files = win.files.concat(f); event.accepted = true }
                        }
                    }
                    onAccepted: {
                        if (text.trim() || win.files.length) win.s.send("text", { text: text.trim(), files: win.files })
                        text = ""; win.files = []
                    }
                }
                IconButton { glyph: "send"; size: 44; tint: (input.text || win.files.length) ? "#0b1015" : win.s.inkSoft
                    fill: (input.text || win.files.length) ? win.s.led : win.bubble; tip: "Invia"; onClicked: input.accepted() }
                IconButton { glyph: win.busy ? "stop" : "mic"; size: 44; tip: win.busy ? "Ferma" : "Parla"
                    tint: win.busy ? "white" : win.s.ink; fill: win.busy ? "#d9364b" : win.bubble
                    onClicked: win.s.send(win.busy ? "stop" : "listen") }
            }
        }
    }
}
