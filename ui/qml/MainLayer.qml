import QtQuick
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell

// Wayland/KDE: finestre layer-shell (sempre sopra, ancorate in alto, senza bordi).
QtObject {
    id: root
    property Store store: Store {}

    property Window notchWin: Window {
        id: notchWin
        color: "transparent"
        width: notch.implicitWidth
        height: notch.implicitHeight
        visible: false
        LayerShell.Window.scope: "nexus-notch"
        LayerShell.Window.layer: LayerShell.Window.LayerOverlay
        LayerShell.Window.anchors: LayerShell.Window.AnchorTop
        LayerShell.Window.exclusionZone: -1
        LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand
        Notch { id: notch; store: root.store; anchors.fill: parent; visible: !root.store.fullscreen }
        onClosing: close => close.accepted = false
        Component.onCompleted: visible = true
    }

    // chat salvate: si apre dal pulsante nel notch (al centro, con la tastiera)
    property Window chatWin: ChatWindow {
        store: root.store
        LayerShell.Window.scope: "nexus-chat"
        // nessuna ancora = al centro dello schermo (impostato qui: AnchorNone manca nelle versioni vecchie)
        Component.onCompleted: LayerShell.Window.anchors = 0
        LayerShell.Window.layer: LayerShell.Window.LayerTop
        LayerShell.Window.exclusionZone: -1
        LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand
    }

    // primo avvio (AppImage): scegli dove gira il cervello
    property Window setupWin: Window {
        id: setupWin
        color: "transparent"
        width: setupBox.implicitWidth
        height: setupBox.implicitHeight
        visible: root.store.connected && root.store.config.setup_done === false
        LayerShell.Window.scope: "nexus-setup"
        // nessuna ancora = al centro dello schermo (impostato qui: AnchorNone manca nelle versioni vecchie)
        Component.onCompleted: LayerShell.Window.anchors = 0
        LayerShell.Window.layer: LayerShell.Window.LayerOverlay
        LayerShell.Window.exclusionZone: -1
        LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityOnDemand
        Setup { id: setupBox; s: root.store; anchors.fill: parent }
        onClosing: close => close.accepted = false
    }

    property Window faceWin: Window {
        id: faceWin
        color: "transparent"
        visible: false
        LayerShell.Window.scope: "nexus-face"
        LayerShell.Window.layer: LayerShell.Window.LayerTop
        LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                                   | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
        LayerShell.Window.exclusionZone: -1
        LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityExclusive
        Face { store: root.store; anchors.fill: parent }
        onClosing: close => { close.accepted = false; root.store.fullscreen = false }
    }

    property Connections fsWatch: Connections {
        target: root.store
        function onFullscreenChanged() { faceWin.visible = root.store.fullscreen; notchWin.visible = !root.store.fullscreen }
    }
    Component.onCompleted: Qt.callLater(function() { faceWin.visible = root.store.fullscreen; notchWin.visible = !root.store.fullscreen })
}
