import QtQuick
import QtQuick.Window

// Ripiego senza layer-shell (X11 o plugin mancante): finestre normali senza bordi.
QtObject {
    id: root
    property Store store: Store {}

    property Window notchWin: Window {
        id: notchWin
        objectName: "nexusNotch"
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        width: notch.implicitWidth
        height: notch.implicitHeight
        x: (Screen.width - width) / 2
        y: 0
        visible: true
        Notch { id: notch; store: root.store; anchors.fill: parent; visible: !root.store.fullscreen }
        onClosing: close => close.accepted = false
    }

    property Window faceWin: Window {
        id: faceWin
        objectName: "nexusFace"
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        visible: false
        Face { store: root.store; anchors.fill: parent }
        onClosing: close => { close.accepted = false; root.store.fullscreen = false }
    }

    // primo avvio (Windows e AppImage): scegli dove gira il cervello
    // chat salvate: si apre dal pulsante nel notch
    property Window chatWin: ChatWindow { store: root.store }

    property Window setupWin: Window {
        id: setupWin
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        title: "NEXUS"
        width: setupBox.implicitWidth
        height: setupBox.implicitHeight
        x: (Screen.width - width) / 2
        y: (Screen.height - height) / 2
        visible: root.store.connected && root.store.config.setup_done === false
        Setup { id: setupBox; s: root.store; anchors.fill: parent }
        onClosing: close => close.accepted = false
    }

    property Connections fsWatch: Connections {
        target: root.store
        function onFullscreenChanged() {
            if (root.store.fullscreen) faceWin.showFullScreen(); else faceWin.hide()
        }
    }
    Component.onCompleted: if (root.store.fullscreen) faceWin.showFullScreen()

    // chiamata da app.py quando uno schermo sparisce e torna (coperchio chiuso, sospensione, monitor staccato)
    function reviveWindows() {
        notchWin.visible = false
        reviveLater.restart()
    }
    property Timer reviveLater: Timer {
        interval: 400
        onTriggered: { notchWin.visible = true; if (root.store.fullscreen) faceWin.showFullScreen() }
    }
}
