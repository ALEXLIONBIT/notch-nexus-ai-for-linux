import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Selettore di colore: quadrato saturazione/luminosità + barra della tinta + codice esadecimale.
Rectangle {
    id: picker
    required property var store
    property color value: "#9be7ff"
    property string title: "Colore"
    property bool allowReset: false
    signal picked(color c)
    signal reset()
    signal closed()

    property real h: 0.5
    property real sat: 0.4
    property real val: 1
    function load(c) { value = c; h = Math.max(0, c.hsvHue); sat = c.hsvSaturation; val = c.hsvValue }
    function emitColor() { value = Qt.hsva(h, sat, val, 1); picked(value) }

    width: 320; height: col.implicitHeight + 36
    radius: 22
    color: store.dark ? "#262a31" : "#ffffff"
    border.color: store.dark ? "#3a3f48" : "#e3e7eb"
    MouseArea { anchors.fill: parent }   // non far passare i click sotto

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Text { text: picker.title; color: picker.store.ink; font { family: picker.store.sansFamily; pixelSize: 16; weight: Font.Bold } Layout.fillWidth: true }
            IconButton { glyph: "close"; tint: picker.store.ink; size: 30; onClicked: picker.closed() }
        }
        // saturazione (x) / luminosità (y)
        Rectangle {
            id: sv
            Layout.fillWidth: true; Layout.preferredHeight: 170
            radius: 12
            color: Qt.hsva(picker.h, 1, 1, 1)
            Rectangle { anchors.fill: parent; radius: 12
                gradient: Gradient { orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: "transparent" } } }
            Rectangle { anchors.fill: parent; radius: 12
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" } GradientStop { position: 1; color: "black" } } }
            Rectangle {
                width: 18; height: 18; radius: 9
                x: picker.sat * sv.width - 9; y: (1 - picker.val) * sv.height - 9
                color: picker.value; border.color: "white"; border.width: 3
            }
            MouseArea {
                anchors.fill: parent
                function upd(m) {
                    picker.sat = Math.max(0, Math.min(1, m.x / width))
                    picker.val = Math.max(0, Math.min(1, 1 - m.y / height))
                    picker.emitColor()
                }
                onPressed: m => upd(m)
                onPositionChanged: m => upd(m)
            }
        }
        // tinta
        Rectangle {
            id: hue
            Layout.fillWidth: true; Layout.preferredHeight: 18
            radius: 9
            gradient: Gradient { orientation: Gradient.Horizontal
                GradientStop { position: 0.00; color: "#ff0000" } GradientStop { position: 0.17; color: "#ffff00" }
                GradientStop { position: 0.33; color: "#00ff00" } GradientStop { position: 0.50; color: "#00ffff" }
                GradientStop { position: 0.67; color: "#0000ff" } GradientStop { position: 0.83; color: "#ff00ff" }
                GradientStop { position: 1.00; color: "#ff0000" } }
            Rectangle { width: 22; height: 22; radius: 11; y: -2; x: picker.h * hue.width - 11
                color: Qt.hsva(picker.h, 1, 1, 1); border.color: "white"; border.width: 3 }
            MouseArea {
                anchors.fill: parent; anchors.margins: -6
                function upd(m) { picker.h = Math.max(0, Math.min(0.999, (m.x - 6) / hue.width)); picker.emitColor() }
                onPressed: m => upd(m)
                onPositionChanged: m => upd(m)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Rectangle { width: 36; height: 36; radius: 18; color: picker.value; border.color: picker.store.inkSoft; border.width: 1 }
            TextField {
                id: hex
                Layout.fillWidth: true
                text: picker.value.toString().toUpperCase()
                color: picker.store.ink; font { family: picker.store.sansFamily; pixelSize: 14; weight: Font.DemiBold }
                leftPadding: 12
                background: Rectangle { implicitHeight: 36; radius: 18; color: picker.store.dark ? "#1c1f24" : "#eef1f4" }
                onEditingFinished: {
                    var t = text.trim(); if (t[0] !== "#") t = "#" + t
                    if (/^#[0-9a-fA-F]{6}$/.test(t)) { picker.load(t); picker.picked(picker.value) }
                }
            }
        }
        IconButton {
            visible: picker.allowReset
            text: "Usa il colore del tema"; tint: picker.store.ink; size: 34
            fill: picker.store.dark ? "#1c1f24" : "#eef1f4"
            Layout.fillWidth: true
            onClicked: picker.reset()
        }
    }
}
