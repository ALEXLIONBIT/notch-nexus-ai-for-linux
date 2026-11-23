import QtQuick
import QtQuick.Window

// Ripiego senza layer-shell (X11 o plugin mancante): finestre normali senza bordi.
QtObject {
    id: root
    property Store store: Store {}

    property Window notchWin: Window {
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        width: notch.implicitWidth
        height: notch.implicitHeight
        x: (Screen.width - width) / 2
        y: 0
        visible: true
        Notch { id: notch; store: root.store; anchors.fill: parent; visible: !root.store.fullscreen }
    }

    property Window faceWin: Window {
        id: faceWin
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        visible: false
        Face { store: root.store; anchors.fill: parent }
    }

    property Connections fsWatch: Connections {
        target: root.store
        function onFullscreenChanged() {
            if (root.store.fullscreen) faceWin.showFullScreen(); else faceWin.hide()
        }
    }
    Component.onCompleted: if (root.store.fullscreen) faceWin.showFullScreen()
}
