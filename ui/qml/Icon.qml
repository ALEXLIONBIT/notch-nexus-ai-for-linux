import QtQuick

// Icone disegnate a mano (tratto arrotondato), così restano nitide a ogni scala.
Canvas {
    id: ic
    property string name: "mic"
    property color color: "white"
    property real stroke: 1.8
    implicitWidth: 18; implicitHeight: 18
    onNameChanged: requestPaint()
    onColorChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset()
        var s = width / 18
        c.scale(s, s)
        c.strokeStyle = color; c.fillStyle = color
        c.lineWidth = stroke; c.lineCap = "round"; c.lineJoin = "round"
        c.beginPath()
        switch (name) {
        case "mic":
            c.roundedRect(6.5, 2, 5, 9, 2.5, 2.5); c.stroke()
            c.beginPath(); c.moveTo(4, 8.5); c.bezierCurveTo(4, 14, 14, 14, 14, 8.5); c.stroke()
            c.beginPath(); c.moveTo(9, 13.2); c.lineTo(9, 16); c.stroke()
            break
        case "stop":
            c.roundedRect(4.5, 4.5, 9, 9, 2, 2); c.fill(); break
        case "expand":
            c.moveTo(3, 7); c.lineTo(3, 3); c.lineTo(7, 3)
            c.moveTo(11, 3); c.lineTo(15, 3); c.lineTo(15, 7)
            c.moveTo(15, 11); c.lineTo(15, 15); c.lineTo(11, 15)
            c.moveTo(7, 15); c.lineTo(3, 15); c.lineTo(3, 11); c.stroke(); break
        case "pin":
            c.arc(9, 7, 3.6, 0, 6.2832); c.stroke()
            c.beginPath(); c.moveTo(9, 10.6); c.lineTo(9, 16); c.stroke(); break
        case "pinned":
            c.arc(9, 7, 3.6, 0, 6.2832); c.fill()
            c.beginPath(); c.moveTo(9, 10.6); c.lineTo(9, 16); c.stroke(); break
        case "gear":
            c.arc(9, 9, 2.6, 0, 6.2832); c.stroke()
            for (var i = 0; i < 8; i++) {
                var a = i * Math.PI / 4
                c.beginPath(); c.moveTo(9 + Math.cos(a) * 5, 9 + Math.sin(a) * 5)
                c.lineTo(9 + Math.cos(a) * 7, 9 + Math.sin(a) * 7); c.stroke()
            }
            c.beginPath(); c.arc(9, 9, 5, 0, 6.2832); c.stroke(); break
        case "close":
            c.moveTo(4.5, 4.5); c.lineTo(13.5, 13.5); c.moveTo(13.5, 4.5); c.lineTo(4.5, 13.5); c.stroke(); break
        case "send":
            c.moveTo(3, 9); c.lineTo(15, 9); c.moveTo(10, 4); c.lineTo(15, 9); c.lineTo(10, 14); c.stroke(); break
        case "chat":
            c.roundedRect(2.5, 3, 13, 9.5, 3, 3); c.stroke()
            c.beginPath(); c.moveTo(6, 12.5); c.lineTo(5, 15.5); c.lineTo(9.5, 12.5); c.stroke(); break
        case "plus":
            c.moveTo(9, 3.5); c.lineTo(9, 14.5); c.moveTo(3.5, 9); c.lineTo(14.5, 9); c.stroke(); break
        case "search":
            c.arc(8, 8, 4.6, 0, 6.2832); c.stroke()
            c.beginPath(); c.moveTo(11.4, 11.4); c.lineTo(15, 15); c.stroke(); break
        case "check":
            c.moveTo(3.5, 9.5); c.lineTo(7.5, 13.5); c.lineTo(14.5, 5); c.stroke(); break
        }
    }
}
