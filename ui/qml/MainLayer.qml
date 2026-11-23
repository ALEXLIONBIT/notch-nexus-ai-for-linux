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
        Component.onCompleted: visible = true
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
    }

    property Connections fsWatch: Connections {
        target: root.store
        function onFullscreenChanged() { faceWin.visible = root.store.fullscreen; notchWin.visible = !root.store.fullscreen }
    }
    Component.onCompleted: Qt.callLater(function() { faceWin.visible = root.store.fullscreen; notchWin.visible = !root.store.fullscreen })
}
