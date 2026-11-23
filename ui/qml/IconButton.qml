import QtQuick
import QtQuick.Controls

AbstractButton {
    id: b
    property string glyph: "mic"
    property color tint: "white"
    property color fill: "transparent"
    property string tip: ""
    property real size: 30
    implicitWidth: text !== "" ? label.implicitWidth + 28 : size
    implicitHeight: size
    hoverEnabled: true
    focusPolicy: Qt.TabFocus

    contentItem: Item {
        Icon {
            visible: b.text === ""
            anchors.centerIn: parent
            width: b.size * 0.55; height: width
            name: b.glyph; color: b.tint
        }
        Text {
            id: label
            visible: b.text !== ""
            anchors.centerIn: parent
            text: b.text; color: b.tint
            font.pixelSize: b.size * 0.42; font.weight: Font.DemiBold
        }
    }
    background: Rectangle {
        radius: height / 2
        color: b.fill !== Qt.color("transparent") ? b.fill
             : b.pressed ? Qt.rgba(1, 1, 1, 0.16) : b.hovered ? Qt.rgba(1, 1, 1, 0.09) : "transparent"
        border.width: b.visualFocus ? 2 : 0
        border.color: b.tint
        scale: b.pressed ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: 90 } }
    }
    ToolTip.visible: hovered && tip !== ""
    ToolTip.text: tip
    ToolTip.delay: 600
}
