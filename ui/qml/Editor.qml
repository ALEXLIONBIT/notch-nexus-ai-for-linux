import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

// Editor "Disegna il tuo robot": accendi i LED con il mouse, con più colori.
// L'occhio vale per entrambi gli occhi (e continua a sbattere/guardarsi intorno), la bocca per quando sta zitto.
Rectangle {
    id: ed
    required property var store
    readonly property var s: store
    color: Qt.rgba(0, 0, 0, 0.55)
    MouseArea { anchors.fill: parent; onClicked: {} }

    property int brush: 1          // 0 = gomma, 1 = principale, 2..8 tavolozza
    property int editIndex: -1     // colore della tavolozza in modifica

    function setCell(which, idx, v) {
        var str = which === "eye" ? s.customEye : s.customMouth
        if (str.charAt(idx) === String(v)) return
        str = str.substring(0, idx) + v + str.substring(idx + 1)
        if (which === "eye") s.customEye = str; else s.customMouth = str
    }
    function fill(which, v) {
        var n = which === "eye" ? s.eyeCols * s.eyeRows : s.mouthCols * s.mouthRows
        var str = ""; for (var i = 0; i < n; i++) str += v
        if (which === "eye") s.customEye = str; else s.customMouth = str
    }
    function mirrorEye() {     // copia la metà sinistra sulla destra
        var str = s.customEye.split(""), c = s.eyeCols
        for (var r = 0; r < s.eyeRows; r++)
            for (var x = 0; x < Math.floor(c / 2); x++) str[r * c + (c - 1 - x)] = str[r * c + x]
        s.customEye = str.join("")
    }

    component PaintGrid: Item {
        id: pg
        property string which: "eye"
        property int nc: 9
        property int nr: 9
        readonly property string cells: which === "eye" ? ed.s.customEye : ed.s.customMouth
        readonly property real cell: Math.min(width / nc, height / nr)
        implicitHeight: width * nr / nc
        Rectangle { anchors.fill: parent; anchors.margins: -12; radius: 18; color: ed.s.glass }
        Repeater {
            model: pg.nc * pg.nr
            Rectangle {
                readonly property int v: parseInt(pg.cells.charAt(index)) || 0
                x: (index % pg.nc) * pg.cell + pg.cell * 0.1
                y: Math.floor(index / pg.nc) * pg.cell + pg.cell * 0.1
                width: pg.cell * 0.8; height: width
                radius: ed.s.dotShape === "quadrati" ? width * 0.15 : width / 2
                color: v === 0 ? ed.s.ledOff : ed.s.paletteColor(v)
                border.color: Qt.rgba(1, 1, 1, 0.06); border.width: 1
            }
        }
        MouseArea {
            anchors.fill: parent
            property int paintValue: 1
            function at(m) {
                var cx = Math.floor(m.x / pg.cell), cy = Math.floor(m.y / pg.cell)
                if (cx < 0 || cy < 0 || cx >= pg.nc || cy >= pg.nr) return -1
                return cy * pg.nc + cx
            }
            onPressed: m => {
                var i = at(m); if (i < 0) return
                // clic su un LED già di quel colore = lo spegne
                var cur = parseInt(pg.cells.charAt(i)) || 0
                paintValue = (cur === ed.brush && ed.brush !== 0) ? 0 : ed.brush
                ed.setCell(pg.which, i, paintValue)
            }
            onPositionChanged: m => { var i = at(m); if (i >= 0) ed.setCell(pg.which, i, paintValue) }
        }
    }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.86, 1240); height: Math.min(parent.height * 0.86, 820)
        radius: 30
        color: ed.s.dark ? "#1d2126" : "#ffffff"
        layer.enabled: true
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#000000"; shadowOpacity: 0.4; shadowBlur: 1; blurMax: 64; shadowVerticalOffset: 20; shadowHorizontalOffset: 0 }

        ColumnLayout {
            anchors.fill: parent; anchors.margins: 34
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 2
                    Text { text: "Disegna il tuo robot"; color: ed.s.ink; font { family: ed.s.sansFamily; pixelSize: 28; weight: Font.ExtraBold } }
                    Text { text: "Scegli un colore e trascina sui LED. Clic su un LED dello stesso colore per spegnerlo."
                           color: ed.s.inkSoft; font { family: ed.s.sansFamily; pixelSize: 14 } }
                }
                Item { Layout.fillWidth: true }
                IconButton { text: "Fatto"; size: 42; tint: "#0b1015"; fill: ed.s.led; onClicked: ed.s.editorOpen = false }
            }

            // tavolozza
            RowLayout {
                spacing: 10
                Text { text: "Colore"; color: ed.s.inkSoft; font { family: ed.s.sansFamily; pixelSize: 14; weight: Font.DemiBold } }
                Repeater {
                    model: 9
                    Rectangle {
                        width: 42; height: 42; radius: 21
                        color: index === 0 ? "transparent" : ed.s.paletteColor(index)
                        border.width: ed.brush === index ? 3 : 1
                        border.color: ed.brush === index ? ed.s.ink : ed.s.inkSoft
                        Icon { visible: index === 0; anchors.centerIn: parent; width: 18; height: 18; name: "close"; color: ed.s.inkSoft }
                        Text { visible: index === 1; anchors.centerIn: parent; text: "1"; color: "#0b1015"; font { pixelSize: 13; weight: Font.Bold } }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (ed.brush === index && index > 0) {     // secondo clic = cambia questo colore
                                    ed.editIndex = index
                                    picker.title = index === 1 ? "Colore principale" : "Colore " + index
                                    picker.load(ed.s.paletteColor(index))
                                }
                                ed.brush = index
                            }
                        }
                        ToolTip.visible: hh.hovered
                        ToolTip.text: index === 0 ? "Gomma" : index === 1 ? "Colore principale (clicca di nuovo per cambiarlo)" : "Clicca di nuovo per cambiarlo"
                        ToolTip.delay: 500
                        HoverHandler { id: hh }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: 40
                // occhio
                ColumnLayout {
                    Layout.preferredWidth: 1; Layout.fillWidth: true; Layout.fillHeight: true
                    spacing: 14
                    Text { text: "Occhio"; color: ed.s.ink; font { family: ed.s.sansFamily; pixelSize: 18; weight: Font.Bold } }
                    Item {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        PaintGrid { which: "eye"; nc: ed.s.eyeCols; nr: ed.s.eyeRows
                            width: Math.min(parent.width, parent.height) - 24; anchors.centerIn: parent }
                    }
                    RowLayout {
                        spacing: 8
                        IconButton { text: "Specchia"; size: 34; tint: ed.s.ink; fill: ed.s.dark ? "#2a2f36" : "#eef1f4"; onClicked: ed.mirrorEye() }
                        IconButton { text: "Riempi"; size: 34; tint: ed.s.ink; fill: ed.s.dark ? "#2a2f36" : "#eef1f4"; onClicked: ed.fill("eye", ed.brush) }
                        IconButton { text: "Pulisci"; size: 34; tint: ed.s.ink; fill: ed.s.dark ? "#2a2f36" : "#eef1f4"; onClicked: ed.fill("eye", 0) }
                    }
                }
                // bocca + anteprima
                ColumnLayout {
                    Layout.preferredWidth: 1; Layout.fillWidth: true; Layout.fillHeight: true
                    spacing: 14
                    Text { text: "Bocca"; color: ed.s.ink; font { family: ed.s.sansFamily; pixelSize: 18; weight: Font.Bold } }
                    PaintGrid { which: "mouth"; nc: ed.s.mouthCols; nr: ed.s.mouthRows; Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12 }
                    RowLayout {
                        spacing: 8
                        IconButton { text: "Pulisci"; size: 34; tint: ed.s.ink; fill: ed.s.dark ? "#2a2f36" : "#eef1f4"; onClicked: ed.fill("mouth", 0) }
                    }
                    Text { text: "Anteprima"; color: ed.s.ink; font { family: ed.s.sansFamily; pixelSize: 18; weight: Font.Bold } Layout.topMargin: 8 }
                    Rectangle {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        radius: 24; color: ed.s.glass
                        DotFace { store: ed.s; forceMood: "idle"; cols: 34; rows: 15
                            width: Math.min(parent.width * 0.9, parent.height * 0.85 * cols / rows); height: width * rows / cols
                            anchors.centerIn: parent }
                    }
                }
            }
        }
    }

    ColorPicker {
        id: picker
        store: ed.s
        visible: ed.editIndex > 0
        anchors.centerIn: parent
        onPicked: c => { if (ed.editIndex === 1) ed.s.led = c; else ed.s.setPaletteColor(ed.editIndex, c) }
        onClosed: ed.editIndex = -1
    }

    Component.onCompleted: { s.eyeStyle = "disegnati"; s.mouthStyle = "disegnata" }
}
