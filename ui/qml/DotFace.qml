import QtQuick

// Volto del robot su una matrice di LED a puntini. Ogni stato ha la sua espressione.
// Usato grande nel casco, piccolo nel notch e nell'anteprima (cambiano solo cols/rows).
Canvas {
    id: face
    required property var store
    property int cols: 34
    property int rows: 15
    property bool glow: true
    property color led: store.led
    property color off: store.ledOff
    // per l'editor: forzano stile/stato senza toccare le preferenze
    property string forceMood: ""

    property real t: 0
    property real blink: 1
    readonly property var cur: ({ c: 0 })   // colore del puntino in calcolo: 0/1 principale, 2..8 tavolozza, -1 secondario
    property color accent: store.accentColor
    property real lvl: 0
    readonly property string mood: forceMood !== "" ? forceMood : (store.happy ? "happy" : store.st)

    implicitHeight: width * rows / cols
    renderTarget: Canvas.FramebufferObject
    renderStrategy: Canvas.Cooperative

    Timer {
        interval: 33; repeat: true; running: face.visible
        onTriggered: {
            face.t += 0.033
            face.lvl += (face.store.level - face.lvl) * 0.45
            face.requestPaint()
        }
    }
    Timer {
        interval: 3200; repeat: true; running: face.visible
        onTriggered: { interval = 2400 + Math.random() * 3600; blinkAnim.restart() }
    }
    SequentialAnimation {
        id: blinkAnim
        NumberAnimation { target: face; property: "blink"; to: 0.05; duration: 60 }
        NumberAnimation { target: face; property: "blink"; to: 1; duration: 120 }
    }

    // pattern disegnato: campiona in coordinate normalizzate (-1..1), così scala a ogni dimensione
    function samplePattern(pat, pc, pr, u, v) {
        if (u < -1 || u > 1 || v < -1 || v > 1) return 0
        var c = Math.min(pc - 1, Math.floor((u + 1) / 2 * pc))
        var r = Math.min(pr - 1, Math.floor((v + 1) / 2 * pr))
        var d = parseInt(pat.charAt(r * pc + c)) || 0
        if (d > 0) face.cur.c = d
        return d > 0 ? 1 : 0
    }

    function eyeAt(x, y, cx, cy, rx, ry, open, style) {
        var dx = x - cx, dy = y - cy
        var ryo = ry * open
        if (ryo < 0.5) return Math.abs(dy) < 0.5 && Math.abs(dx) <= rx ? 1 : 0
        var u = dx / rx, v = dy / ryo
        switch (style) {
        case "quadrati":
            return (Math.abs(u) <= 1 && Math.abs(v) <= 1 && !(Math.abs(u) > 0.75 && Math.abs(v) > 0.75)) ? 1 : 0
        case "linee":
            return (Math.abs(dy) <= Math.max(0.5, ryo * 0.32) && Math.abs(dx) <= rx * 1.25) ? 1 : 0
        case "triangoli":       // occhi da zucca: punta in alto
            return (v >= -1 && v <= 1 && Math.abs(u) <= (v + 1) / 2 + 0.08) ? 1 : 0
        case "cuori":
            var hx = u * 1.25, hy = -v * 1.25 + 0.25
            var q = hx * hx + hy * hy - 1
            return (q * q * q - hx * hx * hy * hy * hy <= 0) ? 1 : 0
        case "disegnati":
            return samplePattern(store.customEye, store.eyeCols, store.eyeRows, u, v)
        default:
            var d = u * u + v * v
            return d <= 1 ? 1 : (d <= 1.25 ? 0.35 : 0)
        }
    }

    function happyEye(x, y, cx, cy, rx) {
        var dx = x - cx, dy = y - cy
        var curve = -rx * 0.75 + Math.abs(dx) * 0.75
        return (Math.abs(dx) <= rx && Math.abs(dy - curve) < 0.6) ? 1 : 0
    }
    function xEye(x, y, cx, cy, r) {
        var dx = x - cx, dy = y - cy
        return (Math.abs(dx) <= r && Math.abs(dy) <= r && (Math.abs(dx - dy) < 0.6 || Math.abs(dx + dy) < 0.6)) ? 1 : 0
    }

    function idleMouth(x, y, mc, my, mw, happy) {
        var dxm = x - mc, style = store.mouthStyle
        if (happy && style !== "disegnata") style = "sorriso"
        switch (style) {
        case "linea":
            return (Math.round(y) === Math.round(my) && Math.abs(dxm) <= mw * 0.55) ? 1 : 0
        case "o":
            var rr = Math.max(1, rows * 0.09), d = Math.sqrt(dxm * dxm + (y - my) * (y - my))
            return Math.abs(d - rr) < 0.6 ? 1 : 0
        case "zigzag":          // denti da zucca
            if (Math.abs(dxm) > mw) return 0
            var zz = my + ((Math.round(x) % 2) === 0 ? -0.5 : 0.5)
            return Math.abs(y - zz) < 0.6 ? 1 : 0
        case "disegnata":
            var mh = Math.max(1.5, rows * 0.16)
            return samplePattern(store.customMouth, store.mouthCols, store.mouthRows, dxm / (mw * 1.25), (y - my + 0.5) / mh)
        default:
            var sw = happy ? mw : mw * 0.6
            if (Math.abs(dxm) > sw) return 0
            var sy = my + (1 - (dxm * dxm) / (sw * sw)) * (happy ? 1.8 : 1.3) - 0.6
            return Math.abs(y - sy) < 0.55 ? 1 : 0
        }
    }

    function lit(x, y) {
        var c = cols, r = rows, t = face.t, mood = face.mood
        var ex1 = c * 0.29, ex2 = c * 0.71, ey = r * 0.40
        var rx = Math.max(1.2, c * 0.105), ry = Math.max(1.2, r * 0.25)
        var look = 0, open = 1
        if (mood === "listening") open = 1.12
        else if (mood === "thinking") { open = 0.55; look = Math.sin(t * 2.2) * c * 0.06 }
        else if (mood === "acting") { open = 0.7; look = c * 0.04 }
        else if (mood === "speaking") open = 0.92 - face.lvl * 0.2
        else if (mood === "loading") open = 0.25
        open *= face.blink

        var e = 0
        if (mood === "error") e = Math.max(xEye(x, y, ex1, ey, rx * 0.8), xEye(x, y, ex2, ey, rx * 0.8))
        else if (mood === "happy" && store.eyeStyle !== "disegnati") e = Math.max(happyEye(x, y, ex1, ey, rx), happyEye(x, y, ex2, ey, rx))
        else e = Math.max(eyeAt(x, y, ex1 + look, ey, rx, ry, open, store.eyeStyle),
                          eyeAt(x, y, ex2 + look, ey, rx, ry, open, store.eyeStyle))
        if (e > 0) return e

        var my = r * 0.80, mw = c * 0.17, mc = (c - 1) / 2, dxm = x - mc
        face.cur.c = -1
        if (mood === "speaking" || mood === "listening") {
            if (Math.abs(dxm) > mw) return 0
            var mid = 1 - Math.abs(dxm) / (mw + 1)
            var wob = 0.6 + 0.4 * Math.sin(t * 9 + x * 1.7)
            var h = Math.max(0, face.lvl * 1.5 * mid * wob * r * 0.16)
            return Math.abs(y - my) <= h + 0.01 ? 1 : 0
        }
        if (mood === "thinking" || mood === "acting" || mood === "loading") {
            var k = Math.floor(t * (mood === "acting" ? 10 : 6)) % 3
            if (Math.round(y) !== Math.round(my)) return 0
            for (var i = 0; i < 3; i++)
                if (Math.round(x) === Math.round(mc - 2 + i * 2)) return i === k ? 1 : 0.3
            return 0
        }
        if (mood === "error") return (Math.round(y) === Math.round(my) && Math.abs(dxm) <= mw * 0.6) ? 0.8 : 0
        return idleMouth(x, y, mc, my, mw, mood === "happy")
    }

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var cw = width / cols, ch = height / rows
        var cell = Math.min(cw, ch)
        var rad = cell * 0.34
        var square = store.dotShape === "quadrati"
        var g = glow ? store.glowAmount : 0
        var breathe = store.st === "idle" && forceMood === "" ? 0.88 + 0.12 * Math.sin(t * 1.6) : 1
        var on = face.led, acc = face.accent
        var pal = []
        for (var i = 0; i <= 8; i++) pal.push(store.paletteColor(i))
        function dot(px, py, r) {
            ctx.beginPath()
            if (square) ctx.rect(px - r, py - r, r * 2, r * 2)
            else ctx.arc(px, py, r, 0, 6.2832)
            ctx.fill()
        }
        for (var y = 0; y < rows; y++) {
            for (var x = 0; x < cols; x++) {
                var px = (x + 0.5) * cw, py = (y + 0.5) * ch
                face.cur.c = 0
                var b = lit(x, y) * breathe
                var col = face.cur.c >= 2 ? pal[face.cur.c] : face.cur.c === -1 ? acc : on
                if (b > 0 && g > 0) {
                    ctx.globalAlpha = 0.36 * b * g
                    ctx.fillStyle = col
                    dot(px, py, rad * (square ? 1.7 : 2.1))
                }
                ctx.globalAlpha = 1
                ctx.fillStyle = face.off
                dot(px, py, square ? rad * 1.15 : rad)
                if (b > 0) {
                    ctx.globalAlpha = b
                    ctx.fillStyle = col
                    dot(px, py, square ? rad * 1.15 : rad)
                }
            }
        }
        ctx.globalAlpha = 1
    }
}
