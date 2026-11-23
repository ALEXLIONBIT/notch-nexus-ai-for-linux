import QtQuick
import QtCore

// Stato condiviso tra notch e casco + palette, alimentato dagli eventi del backend.
Item {
    id: store
    property string st: "loading"
    property string detail: "Mi sto accendendo"
    property string transcript: ""
    property string reply: ""
    property real level: 0
    property string image: ""
    property string confirmId: ""
    property string confirmText: ""
    property var config: ({})
    property var browsers: []            // [{id, name}] trovati dal backend
    property var presets: ({})           // tipi di provider (Ollama, OpenAI, Groq…)
    property var providerModels: []      // modelli caricati dal provider in modifica
    property string providerMsg: ""
    property var update: ({ current: "", behind: 0, news: [], error: "" })
    property bool providerOk: true
    property string platform: Qt.platform.os === "windows" ? "windows" : "linux"
    property string appVersion: ""
    property var setup: ({ text: "", pct: -1, done: false, error: "", working: false })
    property bool connected: nexus.connected
    property bool fullscreen: false
    property bool settingsOpen: false
    property bool happy: false
    property alias steps: stepsModel

    // ---- sottotitoli in diretta ----
    property string sayText: ""
    property real sayDur: 0
    property double sayStart: 0
    property real sayProgress: 0
    readonly property bool saying: sayText !== "" && sayProgress < 1.05
    Timer {
        interval: 40; repeat: true; running: store.sayText !== ""
        onTriggered: store.sayProgress = store.sayDur > 0 ? (Date.now() - store.sayStart) / 1000 / store.sayDur : 1
    }
    Timer { id: sayClear; interval: 2500; onTriggered: store.sayText = "" }
    Timer { id: happyOff; interval: 2200; onTriggered: store.happy = false }

    // ---- personalizzazione (salvata in ~/.config/nexus/nexus-ui.conf) ----
    property alias theme: prefs.theme
    property alias led: prefs.led
    property alias eyeStyle: prefs.eyeStyle
    property alias mouthStyle: prefs.mouthStyle
    property alias dotShape: prefs.dotShape
    property alias helmetShape: prefs.helmetShape
    property alias antenna: prefs.antenna
    property alias ears: prefs.ears
    property alias glowAmount: prefs.glowAmount
    property alias customEye: prefs.customEye
    property alias customMouth: prefs.customMouth
    property alias accent: prefs.accent
    property alias shellCustom: prefs.shellCustom
    property alias bgCustom: prefs.bgCustom
    property alias paletteStr: prefs.palette
    // tavolozza per disegnare: indice 1 = colore principale, 2..8 = colori extra
    readonly property var ledPalette: paletteStr.split(",")
    function paletteColor(i) { return i <= 1 ? led : (ledPalette[i - 2] || led) }
    function setPaletteColor(i, c) {
        var p = ledPalette.slice(); p[i - 2] = c.toString(); paletteStr = p.join(",")
    }
    property bool editorOpen: false
    property bool setupWantsProvider: false
    property bool providerEditorRequest: false
    readonly property int eyeCols: 9
    readonly property int eyeRows: 9
    readonly property int mouthCols: 15
    readonly property int mouthRows: 5
    Settings {
        id: prefs
        category: "look"
        property string theme: "perla"         // perla | grafite | oled | natale | halloween | plasma
        property color led: "#9be7ff"
        property string eyeStyle: "tondi"      // tondi | quadrati | linee | triangoli | cuori | disegnati
        property string mouthStyle: "sorriso"  // sorriso | linea | zigzag | o | disegnata
        property string dotShape: "tondi"      // tondi | quadrati
        property string helmetShape: "capsula" // capsula | tondo | tv | cubo
        property string antenna: "nessuna"     // nessuna | una | due
        property bool ears: true
        property real glowAmount: 0.6
        property color accent: "#00000000"       // colore secondario (trasparente = come il principale)
        property color shellCustom: "#00000000"  // colore del guscio (trasparente = quello del tema)
        property color bgCustom: "#00000000"     // colore dello sfondo (trasparente = quello del tema)
        property string palette: "#ff5a6e,#ffc861,#8cf5c8,#ff9fd8,#b9a6ff,#ffffff,#3daee9"
        // occhio 9x9 e bocca 15x5 disegnati a mano: "1" acceso, "0" spento
        property string customEye: "000111000001111100011111110111111111111111111111111111011111110001111100000111000"
        property string customMouth: "000000000000000100000000000001010000000000010001110000011100000001111100000"
    }

    // ---- temi ----
    readonly property var themes: ({
        perla:     { name: "Perla",     dark: false, bg: "#e9ecef", bgDeep: "#d3d9df", glow: "#fbfcfd",
                     shellTop: "#ffffff", shellMid: "#f6f7f8", shellBot: "#dfe3e8", shellLine: "#00000000",
                     shadow: "#8a96a3", shadowOp: 0.45, ink: "#1f242b", inkSoft: "#6b7581",
                     led: "#9be7ff", ledOff: "#141a22", glass: "#07090d", font: "Manrope", deco: "" },
        grafite:   { name: "Grafite",   dark: true, bg: "#16181c", bgDeep: "#0d0f12", glow: "#22262d",
                     shellTop: "#3a3f48", shellMid: "#2a2e35", shellBot: "#202329", shellLine: "#00000000",
                     shadow: "#000000", shadowOp: 0.8, ink: "#eef1f4", inkSoft: "#8d96a1",
                     led: "#9be7ff", ledOff: "#141a22", glass: "#07090d", font: "Manrope", deco: "" },
        oled:      { name: "OLED",      dark: true, bg: "#000000", bgDeep: "#000000", glow: "#000000",
                     shellTop: "#0a0a0a", shellMid: "#050505", shellBot: "#000000", shellLine: "#262626",
                     shadow: "#000000", shadowOp: 0.0, ink: "#ffffff", inkSoft: "#5c5c5c",
                     led: "#ffffff", ledOff: "#0a0a0a", glass: "#000000", font: "Manrope", deco: "" },
        natale:    { name: "Natale",    dark: true, bg: "#0f2a1f", bgDeep: "#06150e", glow: "#1d4a35",
                     shellTop: "#ffffff", shellMid: "#f4f0e8", shellBot: "#d8cfbf", shellLine: "#00000000",
                     shadow: "#000000", shadowOp: 0.55, ink: "#fff6e6", inkSoft: "#9fbfae",
                     led: "#ffd27a", ledOff: "#1a1410", glass: "#0a0806", font: "Manrope", deco: "natale" },
        halloween: { name: "Halloween", dark: true, bg: "#170c24", bgDeep: "#090510", glow: "#2e1846",
                     shellTop: "#ffab4a", shellMid: "#f07a1a", shellBot: "#a8470a", shellLine: "#00000000",
                     shadow: "#000000", shadowOp: 0.7, ink: "#ffe8d2", inkSoft: "#a08cb6",
                     led: "#ffb02e", ledOff: "#1c0f06", glass: "#0d0603", font: "Manrope", deco: "halloween" },
        plasma:    { name: "KDE Plasma", dark: true, bg: "#1b1e20", bgDeep: "#141618", glow: "#2a2e32",
                     shellTop: "#4d5257", shellMid: "#31363b", shellBot: "#232629", shellLine: "#3daee9",
                     shadow: "#000000", shadowOp: 0.6, ink: "#fcfcfc", inkSoft: "#a1a9b1",
                     led: "#3daee9", ledOff: "#16191b", glass: "#0b0d0e", font: "Noto Sans", deco: "" }
    })
    readonly property var th: themes[theme] || themes.perla
    function applyTheme(name) {
        theme = name
        var t = themes[name]
        led = t.led
        if (name === "halloween") { eyeStyle = "triangoli"; mouthStyle = "zigzag" }
        else if (eyeStyle === "triangoli" && mouthStyle === "zigzag") { eyeStyle = "tondi"; mouthStyle = "sorriso" }
    }

    readonly property bool dark: th.dark
    readonly property bool hasShell: shellCustom.a > 0
    readonly property bool hasBg: bgCustom.a > 0
    readonly property color accentColor: accent.a > 0 ? accent : led
    readonly property color bg: hasBg ? bgCustom : th.bg
    readonly property color bgDeep: hasBg ? Qt.darker(bgCustom, 1.35) : th.bgDeep
    readonly property color bgGlow: hasBg ? Qt.lighter(bgCustom, 1.25) : th.glow
    readonly property color shellTop: hasShell ? Qt.lighter(shellCustom, 1.22) : th.shellTop
    readonly property color shellMid: hasShell ? shellCustom : th.shellMid
    readonly property color shellBot: hasShell ? Qt.darker(shellCustom, 1.35) : th.shellBot
    readonly property color shellColor: shellMid
    readonly property color shellEdge: shellTop
    readonly property color shellShadow: th.shadow
    readonly property color ink: th.ink
    readonly property color inkSoft: th.inkSoft
    readonly property color glass: th.glass
    readonly property color ledOff: th.ledOff
    readonly property color listenRed: "#ff5a6e"
    readonly property color thinkAmber: "#ffc861"
    readonly property color stateColor: st === "error" ? listenRed
                                      : st === "listening" ? listenRed
                                      : (st === "thinking" || st === "acting") ? thinkAmber : accentColor

    readonly property string statusText: !connected ? "Non trovo il cervello, riprovo…"
        : st === "listening" ? "Ti ascolto"
        : st === "thinking" ? (detail === "Trascrivo…" ? "Ho capito, un attimo" : "Ci penso")
        : st === "acting" ? (detail || "Lo faccio")
        : st === "speaking" ? "Sto parlando"
        : st === "loading" ? (detail || "Mi sto accendendo")
        : st === "error" ? (detail || "Qualcosa è andato storto")
        : (detail || "Pronto")

    ListModel { id: stepsModel }

    function send(t, d) { nexus.send(t, d || {}) }

    FontLoader { id: dotoFont; source: Qt.resolvedUrl("../fonts/Doto.ttf") }
    readonly property string dotFamily: dotoFont.status === FontLoader.Ready ? dotoFont.font.family : "monospace"
    readonly property string sansFamily: th.font     // Manrope (pesi statici caricati da app.py) o Noto Sans

    // "app.py --face" apre subito il casco a schermo intero
    Component.onCompleted: {
        var a = Qt.application.arguments
        if (a.indexOf("--face") >= 0) fullscreen = true
        if (a.indexOf("--settings") >= 0) settingsOpen = true
        if (a.indexOf("--editor") >= 0) editorOpen = true
        if (a.indexOf("--provider-editor") >= 0) { settingsOpen = true; providerEditorRequest = true }
    }

    Connections {
        target: nexus
        function onEvent(type, d) {
            switch (type) {
            case "state":
                store.st = d.state; store.detail = d.detail || ""
                break
            case "level": store.level = d.v; break
            case "transcript": store.transcript = d.text; break
            case "reply": store.reply = d.text; break
            case "say":
                sayClear.stop()
                if (!d.text) { store.sayText = ""; break }
                store.sayText = d.text; store.sayDur = d.dur
                store.sayStart = Date.now(); store.sayProgress = 0
                if (d.last) { sayClear.interval = d.dur * 1000 + 2500; sayClear.restart() }
                break
            case "step":
                stepsModel.append({ icon: d.icon, text: d.text })
                while (stepsModel.count > 5) stepsModel.remove(0)
                break
            case "image": store.image = "file:///" + d.path.replace(/\\/g, "/").replace(/^\/+/, "") + "?t=" + Date.now(); break
            case "platform": store.platform = d.os; store.appVersion = d.version || ""; break
            case "setup_status":
                store.setup = { text: d.text, pct: d.pct, done: d.done, error: d.error, working: !d.done && !d.error }
                if (d.done && store.setupWantsProvider) { store.settingsOpen = true; store.providerEditorRequest = true; store.fullscreen = true }
                break
            case "confirm": store.confirmId = d.id || ""; store.confirmText = d.text || ""; break
            case "config": store.config = d.config; break
            case "browsers": store.browsers = d.list; break
            case "presets": store.presets = d.presets; break
            case "update_status": store.update = d; break
            case "provider_models": store.providerModels = d.models; store.providerMsg = d.models.length + " modelli trovati"; store.providerOk = true; break
            case "provider_result": store.providerMsg = d.text; store.providerOk = d.ok; break
            case "session":
                if (d.start) {
                    stepsModel.clear(); store.transcript = ""; store.reply = ""; store.image = ""
                    store.happy = false
                } else if (store.reply !== "" && store.st !== "error") {
                    store.happy = true; happyOff.restart()
                }
                break
            }
        }
    }
}
