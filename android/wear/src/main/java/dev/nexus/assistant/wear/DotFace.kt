package dev.nexus.assistant.wear

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.min
import kotlin.math.round
import kotlin.math.sin
import kotlin.math.sqrt

/** Volto del robot su una matrice di LED (stessa logica del PC). */
@Composable
fun DotFace(modifier: Modifier = Modifier, cols: Int = 34, rows: Int = 15, forceMood: String? = null, glow: Boolean = true) {
    var t by remember { mutableFloatStateOf(0f) }
    var blink by remember { mutableFloatStateOf(1f) }
    var lvl by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        var last = 0L; var nextBlink = 3f
        while (true) {
            withFrameNanos { now ->
                val dt = if (last == 0L) 0f else (now - last) / 1e9f
                last = now; t += dt
                lvl += (Core.level - lvl) * 0.35f
                val phase = t - nextBlink
                blink = when { phase < 0f -> 1f; phase < 0.07f -> 0.05f; phase < 0.18f -> 0.5f; else -> { nextBlink = t + 2.4f + (Math.random() * 3.5).toFloat(); 1f } }
            }
        }
    }
    val mood = forceMood ?: if (Core.happy) "happy" else Core.state
    val led = Look.led; val acc = Look.accent; val off = Look.theme.ledOff
    val eyeStyle = Prefs.eyeStyle; val mouthStyle = Prefs.mouthStyle
    val eyePat = Prefs.customEye; val mouthPat = Prefs.customMouth
    val square = Prefs.dotShape == "quadrati"; val g = if (glow) Prefs.glow else 0f
    val pal = (0..8).map { Color(Prefs.paletteColor(it)) }

    Canvas(modifier.aspectRatio(cols.toFloat() / rows)) {
        val cw = size.width / cols; val ch = size.height / rows; val rad = min(cw, ch) * 0.34f
        var cur = 0
        fun sample(pat: String, pc: Int, pr: Int, u: Float, v: Float): Float {
            if (u < -1 || u > 1 || v < -1 || v > 1) return 0f
            val c = min(pc - 1, floor((u + 1) / 2 * pc).toInt()); val r = min(pr - 1, floor((v + 1) / 2 * pr).toInt())
            val d = pat.getOrNull(r * pc + c)?.digitToIntOrNull() ?: 0
            if (d > 0) cur = d
            return if (d > 0) 1f else 0f
        }
        fun eyeAt(x: Float, y: Float, cx: Float, cy: Float, rx: Float, ry: Float, open: Float): Float {
            val dx = x - cx; val dy = y - cy; val ryo = ry * open
            if (ryo < 0.5f) return if (abs(dy) < 0.5f && abs(dx) <= rx) 1f else 0f
            val u = dx / rx; val v = dy / ryo
            return when (eyeStyle) {
                "quadrati" -> if (abs(u) <= 1 && abs(v) <= 1 && !(abs(u) > .75f && abs(v) > .75f)) 1f else 0f
                "linee" -> if (abs(dy) <= maxOf(.5f, ryo * .32f) && abs(dx) <= rx * 1.25f) 1f else 0f
                "triangoli" -> if (v >= -1 && v <= 1 && abs(u) <= (v + 1) / 2 + .08f) 1f else 0f
                "cuori" -> { val hx = u * 1.25f; val hy = -v * 1.25f + .25f; val q = hx * hx + hy * hy - 1; if (q * q * q - hx * hx * hy * hy * hy <= 0) 1f else 0f }
                "disegnati" -> sample(eyePat, Prefs.EYE_COLS, Prefs.EYE_ROWS, u, v)
                else -> { val d = u * u + v * v; if (d <= 1) 1f else if (d <= 1.25f) .35f else 0f }
            }
        }
        fun lit(x: Float, y: Float): Float {
            val c = cols.toFloat(); val r = rows.toFloat()
            val ex1 = c * .29f; val ex2 = c * .71f; val ey = r * .40f
            val rx = maxOf(1.2f, c * .105f); val ry = maxOf(1.2f, r * .25f)
            var look = 0f; var open = 1f
            when (mood) {
                "listening" -> open = 1.12f
                "thinking" -> { open = .55f; look = sin(t * 2.2f) * c * .06f }
                "acting" -> { open = .7f; look = c * .04f }
                "speaking" -> open = .92f - lvl * .2f
            }
            open *= blink
            val e = when {
                mood == "error" -> listOf(ex1, ex2).maxOf { cx -> val dx = x - cx; val dy = y - ey; if (abs(dx) <= rx * .8f && abs(dy) <= rx * .8f && (abs(dx - dy) < .6f || abs(dx + dy) < .6f)) 1f else 0f }
                mood == "happy" && eyeStyle != "disegnati" -> listOf(ex1, ex2).maxOf { cx -> val dx = x - cx; val dy = y - ey; if (abs(dx) <= rx && abs(dy - (-rx * .75f + abs(dx) * .75f)) < .6f) 1f else 0f }
                else -> maxOf(eyeAt(x, y, ex1 + look, ey, rx, ry, open), eyeAt(x, y, ex2 + look, ey, rx, ry, open))
            }
            if (e > 0) return e
            val my = r * .8f; val mw = c * .17f; val mc = (c - 1) / 2; val dxm = x - mc
            cur = -1
            if (mood == "speaking" || mood == "listening") {
                if (abs(dxm) > mw) return 0f
                val mid = 1 - abs(dxm) / (mw + 1); val wob = .6f + .4f * sin(t * 9 + x * 1.7f)
                return if (abs(y - my) <= lvl * 1.5f * mid * wob * r * .16f + .01f) 1f else 0f
            }
            if (mood == "thinking" || mood == "acting") {
                if (round(y) != round(my)) return 0f
                val k = (t * (if (mood == "acting") 10 else 6)).toInt() % 3
                for (i in 0..2) if (round(x) == round(mc - 2 + i * 2)) return if (i == k) 1f else .3f
                return 0f
            }
            if (mood == "error") return if (round(y) == round(my) && abs(dxm) <= mw * .6f) .8f else 0f
            val happy = mood == "happy"
            val style = if (happy && mouthStyle != "disegnata") "sorriso" else mouthStyle
            return when (style) {
                "linea" -> if (round(y) == round(my) && abs(dxm) <= mw * .55f) 1f else 0f
                "o" -> { val rr = maxOf(1f, r * .09f); if (abs(sqrt(dxm * dxm + (y - my) * (y - my)) - rr) < .6f) 1f else 0f }
                "zigzag" -> { if (abs(dxm) > mw) 0f else { val zz = my + (if (round(x).toInt() % 2 == 0) -.5f else .5f); if (abs(y - zz) < .6f) 1f else 0f } }
                "disegnata" -> sample(mouthPat, Prefs.MOUTH_COLS, Prefs.MOUTH_ROWS, dxm / (mw * 1.25f), (y - my + .5f) / maxOf(1.5f, r * .16f))
                else -> { val sw = if (happy) mw else mw * .6f; if (abs(dxm) > sw) 0f else { val sy = my + (1 - dxm * dxm / (sw * sw)) * (if (happy) 1.8f else 1.3f) - .6f; if (abs(y - sy) < .55f) 1f else 0f } }
            }
        }
        val breathe = if (mood == "idle") .88f + .12f * sin(t * 1.6f) else 1f
        for (yy in 0 until rows) for (xx in 0 until cols) {
            val center = Offset((xx + .5f) * cw, (yy + .5f) * ch)
            cur = 0
            val b = lit(xx.toFloat(), yy.toFloat()) * breathe
            val col = when { cur >= 2 -> pal[cur]; cur == -1 -> acc; else -> led }
            fun dot(color: Color, r: Float, alpha: Float) {
                if (square) drawRect(color, Offset(center.x - r, center.y - r), Size(r * 2, r * 2), alpha = alpha)
                else drawCircle(color, r, center, alpha = alpha)
            }
            if (b > 0 && g > 0) dot(col, rad * if (square) 1.7f else 2.1f, .36f * b * g)
            dot(off, if (square) rad * 1.15f else rad, 1f)
            if (b > 0) dot(col, if (square) rad * 1.15f else rad, b.coerceIn(0f, 1f))
        }
    }
}
