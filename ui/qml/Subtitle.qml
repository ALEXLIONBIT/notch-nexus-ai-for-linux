import QtQuick

// Sottotitoli "karaoke": le parole si accendono mentre il robot le pronuncia.
Text {
    id: sub
    required property var store
    property color litColor: "white"
    property color dimColor: Qt.rgba(1, 1, 1, 0.32)
    readonly property string src: store.sayText
    readonly property real p: Math.min(1, store.sayProgress)

    textFormat: Text.StyledText
    wrapMode: Text.Wrap
    text: build(src, p)

    function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
    function build(s, prog) {
        if (!s) return ""
        // avanza per caratteri (le parole lunghe durano di più)
        var cut = Math.round(s.length * prog)
        var end = s.indexOf(" ", cut); if (end < 0) end = s.length
        if (prog <= 0.001) end = 0
        return "<font color='" + litColor + "'>" + esc(s.substring(0, end)) + "</font>"
             + "<font color='" + dimColor + "'>" + esc(s.substring(end)) + "</font>"
    }
}
