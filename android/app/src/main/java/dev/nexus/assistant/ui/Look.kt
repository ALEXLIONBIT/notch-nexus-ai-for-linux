package dev.nexus.assistant.ui

import androidx.compose.ui.graphics.Color
import dev.nexus.assistant.core.Core
import dev.nexus.assistant.core.Prefs

/** I temi, uguali a quelli della versione per PC. */
data class NexusTheme(
    val key: String, val name: String, val dark: Boolean,
    val bg: Color, val bgDeep: Color, val glow: Color,
    val shellTop: Color, val shellMid: Color, val shellBot: Color, val shellLine: Color?,
    val shadowAlpha: Float, val ink: Color, val inkSoft: Color,
    val led: Color, val ledOff: Color, val glass: Color, val deco: String,
)

private fun c(hex: Long) = Color(hex)

val THEMES = listOf(
    NexusTheme("perla", "Perla", false, c(0xFFE9ECEF), c(0xFFD3D9DF), c(0xFFFBFCFD), c(0xFFFFFFFF), c(0xFFF6F7F8), c(0xFFDFE3E8), null, .25f, c(0xFF1F242B), c(0xFF6B7581), c(0xFF9BE7FF), c(0xFF141A22), c(0xFF07090D), ""),
    NexusTheme("grafite", "Grafite", true, c(0xFF16181C), c(0xFF0D0F12), c(0xFF22262D), c(0xFF3A3F48), c(0xFF2A2E35), c(0xFF202329), null, .6f, c(0xFFEEF1F4), c(0xFF8D96A1), c(0xFF9BE7FF), c(0xFF141A22), c(0xFF07090D), ""),
    NexusTheme("oled", "OLED", true, c(0xFF000000), c(0xFF000000), c(0xFF000000), c(0xFF0A0A0A), c(0xFF050505), c(0xFF000000), c(0xFF262626), 0f, c(0xFFFFFFFF), c(0xFF5C5C5C), c(0xFFFFFFFF), c(0xFF0A0A0A), c(0xFF000000), ""),
    NexusTheme("natale", "Natale", true, c(0xFF0F2A1F), c(0xFF06150E), c(0xFF1D4A35), c(0xFFFFFFFF), c(0xFFF4F0E8), c(0xFFD8CFBF), null, .45f, c(0xFFFFF6E6), c(0xFF9FBFAE), c(0xFFFFD27A), c(0xFF1A1410), c(0xFF0A0806), "natale"),
    NexusTheme("halloween", "Halloween", true, c(0xFF170C24), c(0xFF090510), c(0xFF2E1846), c(0xFFFFAB4A), c(0xFFF07A1A), c(0xFFA8470A), null, .5f, c(0xFFFFE8D2), c(0xFFA08CB6), c(0xFFFFB02E), c(0xFF1C0F06), c(0xFF0D0603), "halloween"),
    NexusTheme("plasma", "KDE Plasma", true, c(0xFF1B1E20), c(0xFF141618), c(0xFF2A2E32), c(0xFF4D5257), c(0xFF31363B), c(0xFF232629), c(0xFF3DAEE9), .45f, c(0xFFFCFCFC), c(0xFFA1A9B1), c(0xFF3DAEE9), c(0xFF16191B), c(0xFF0B0D0E), ""),
)

/** Colori effettivi (tema + scelte personali). */
object Look {
    val theme get() = THEMES.firstOrNull { it.key == Prefs.theme } ?: THEMES[1]
    val led get() = Color(Prefs.led)
    val accent get() = if (Prefs.accent != 0) Color(Prefs.accent) else led
    val bg get() = if (Prefs.bgCustom != 0) Color(Prefs.bgCustom) else theme.bg
    val shellMid get() = if (Prefs.shellCustom != 0) Color(Prefs.shellCustom) else theme.shellMid
    val shellTop get() = if (Prefs.shellCustom != 0) lerp(Color(Prefs.shellCustom), Color.White, .25f) else theme.shellTop
    val shellBot get() = if (Prefs.shellCustom != 0) lerp(Color(Prefs.shellCustom), Color.Black, .3f) else theme.shellBot
    val listenRed = Color(0xFFFF5A6E)
    val thinkAmber = Color(0xFFFFC861)
    val stateColor get() = when (Core.state) {
        "error", "listening" -> listenRed
        "thinking", "acting" -> thinkAmber
        else -> accent
    }
    val statusText get() = when (Core.state) {
        "listening" -> "Ti ascolto"
        "thinking" -> Core.detail.ifBlank { "Ci penso" }
        "acting" -> Core.detail.ifBlank { "Lo faccio" }
        "speaking" -> "Sto parlando"
        "error" -> "Qualcosa è andato storto"
        else -> Core.detail.ifBlank { "Pronto" }
    }

    fun applyTheme(key: String) {
        val t = THEMES.first { it.key == key }
        Prefs.theme = key
        Prefs.led = t.led.toArgbInt()
        if (key == "halloween") { Prefs.eyeStyle = "triangoli"; Prefs.mouthStyle = "zigzag" }
        else if (Prefs.eyeStyle == "triangoli" && Prefs.mouthStyle == "zigzag") { Prefs.eyeStyle = "tondi"; Prefs.mouthStyle = "sorriso" }
        Prefs.save()
    }
}

fun lerp(a: Color, b: Color, t: Float) = Color(
    a.red + (b.red - a.red) * t, a.green + (b.green - a.green) * t, a.blue + (b.blue - a.blue) * t, 1f)

fun Color.toArgbInt(): Int = (((alpha * 255).toInt() and 0xFF) shl 24) or (((red * 255).toInt() and 0xFF) shl 16) or
        (((green * 255).toInt() and 0xFF) shl 8) or ((blue * 255).toInt() and 0xFF)
