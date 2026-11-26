import QtQuick

// Allegati in attesa di essere inviati (incollati con Ctrl+V o trascinati): anteprima, nome, ✕ per toglierli.
Flow {
    id: bar
    property var files: []
    property color ink: "#e8edf2"
    property color chip: "#1c232c"
    property string family: ""
    signal removed(int index)
    spacing: 6
    visible: files.length > 0
    Repeater {
        model: bar.files
        Rectangle {
            id: chipBox
            required property var modelData
            required property int index
            readonly property bool isImg: /\.(png|jpe?g|webp|gif|bmp)$/i.test(modelData)
            height: 34; radius: 10; color: bar.chip
            width: row.implicitWidth + 16
            Row {
                id: row
                anchors.centerIn: parent
                spacing: 6
                Image {
                    visible: chipBox.isImg
                    source: chipBox.isImg ? clip.url(chipBox.modelData) : ""
                    width: 26; height: 26; fillMode: Image.PreserveAspectCrop
                    sourceSize.width: 64; asynchronous: true
                }
                Icon { visible: !chipBox.isImg; name: "clip"; color: bar.ink; width: 14; height: 14
                       anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: chipBox.modelData.split(/[\\/]/).pop()
                    color: bar.ink; elide: Text.ElideMiddle
                    width: Math.min(implicitWidth, 170)
                    font { pixelSize: 12; family: bar.family }
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "✕"; color: bar.ink; opacity: 0.7
                    font.pixelSize: 12
                    anchors.verticalCenter: parent.verticalCenter
                    MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor
                                onClicked: bar.removed(chipBox.index) }
                }
            }
        }
    }
}
