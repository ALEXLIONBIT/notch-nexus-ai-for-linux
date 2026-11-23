package dev.nexus.assistant.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.platform.LocalDensity
import dev.nexus.assistant.core.Prefs

data class HelmetShape(val aspect: Float, val r: Float, val vr: Float, val m: Float, val cols: Int, val rows: Int)

val HELMET_SHAPES = mapOf(
    "capsula" to HelmetShape(.60f, .44f, .42f, .085f, 34, 15),
    "tondo" to HelmetShape(.86f, .50f, .50f, .10f, 26, 15),
    "tv" to HelmetShape(.74f, .12f, .07f, .10f, 30, 17),
    "cubo" to HelmetShape(.86f, .22f, .16f, .10f, 28, 17),
)

/** Il casco di NEXUS con visore LED. Lo spazio sopra serve per antenne e cappello. */
@Composable
fun Helmet(modifier: Modifier = Modifier) {
    val sh = HELMET_SHAPES[Prefs.helmetShape] ?: HELMET_SHAPES.getValue("capsula")
    val th = Look.theme
    val boxAspect = 1f / (sh.aspect * 0.84f * 1.45f)
    BoxWithConstraints(modifier.aspectRatio(boxAspect)) {
        val density = LocalDensity.current
        val wPx = with(density) { maxWidth.toPx() }
        val hPx = wPx / boxAspect
        val shellW = wPx * .84f; val shellH = shellW * sh.aspect
        val shellL = (wPx - shellW) / 2; val shellT = hPx - shellH * 1.06f
        val inset = shellH * sh.m
        val visL = shellL + inset; val visT = shellT + inset; val visW = shellW - inset * 2; val visH = shellH - inset * 2
        val stateColor = Look.stateColor; val accent = Look.accent
        val top = Look.shellTop; val mid = Look.shellMid; val bot = Look.shellBot

        Canvas(Modifier.fillMaxSize()) {
            // antenne
            val n = when (Prefs.antenna) { "una" -> 1; "due" -> 2; else -> 0 }
            for (i in 0 until n) {
                val ax = if (n == 1) shellL + shellW / 2 else shellL + shellW * (if (i == 0) .32f else .68f)
                val len = shellH * .32f
                val tilt = if (n == 2) (if (i == 0) -22f else 22f) else 0f
                rotate(tilt, Offset(ax, shellT + shellH * .05f)) {
                    drawLine(bot, Offset(ax, shellT + shellH * .05f), Offset(ax, shellT - len), strokeWidth = shellH * .025f)
                    drawCircle(stateColor.copy(alpha = .35f), shellH * .075f, Offset(ax, shellT - len))
                    drawCircle(stateColor, shellH * .045f, Offset(ax, shellT - len))
                }
            }
            // orecchie
            if (Prefs.ears) {
                val er = shellH * (if (Prefs.helmetShape == "capsula") .15f else .11f)
                for (side in 0..1) {
                    val cx = if (side == 0) shellL + er * .16f else shellL + shellW - er * .16f
                    val cy = shellT + shellH * .42f
                    drawCircle(Brush.verticalGradient(listOf(top, bot), cy - er, cy + er), er, Offset(cx, cy))
                    drawCircle(if (dev.nexus.assistant.core.Core.state == "idle") accent.copy(alpha = .45f) else stateColor, er * .52f, Offset(cx, cy), style = Stroke(er * .14f))
                }
            }
            // ombra + guscio
            val cr = CornerRadius(shellH * sh.r, shellH * sh.r)
            if (th.shadowAlpha > 0f) drawRoundRect(Color.Black.copy(alpha = th.shadowAlpha * .6f), Offset(shellL, shellT + shellH * .06f), Size(shellW, shellH), cr)
            drawRoundRect(Brush.verticalGradient(listOf(top, mid, bot), shellT, shellT + shellH), Offset(shellL, shellT), Size(shellW, shellH), cr)
            th.shellLine?.let { drawRoundRect(it, Offset(shellL, shellT), Size(shellW, shellH), cr, style = Stroke(3f)) }
            if (th.deco == "halloween") for (k in 0 until 5) {
                val w = shellW * (.95f - k * .19f)
                drawRoundRect(Color(0x80501A00), Offset(shellL + (shellW - w) / 2, shellT), Size(w, shellH), CornerRadius(minOf(w, shellH) / 2), style = Stroke(3f), alpha = .55f)
            }
            // visore
            drawRoundRect(th.glass, Offset(visL, visT), Size(visW, visH), CornerRadius(visH * sh.vr, visH * sh.vr))
            val refl = Path().apply {
                moveTo(visL + maxOf(visH * sh.vr * .5f, visW * .04f), visT + visH * .06f)
                lineTo(visL + visW * .55f, visT + visH * .06f); lineTo(visL + visW * .18f, visT + visH * .62f)
                quadraticTo(visL + visW * .02f, visT + visH * .2f, visL + maxOf(visH * sh.vr * .5f, visW * .04f), visT + visH * .06f)
            }
            drawPath(refl, Brush.linearGradient(listOf(Color.White.copy(alpha = if (th.key == "oled") .06f else .14f), Color.Transparent),
                Offset(visL, visT), Offset(visL + visW * .4f, visT + visH * .5f)))
            // accessori dei temi
            if (th.deco == "natale") {
                val hw = shellW * .36f; val hh = hw * .78f; val hx = shellL + shellW * .56f; val hy = shellT - hh * .58f
                rotate(16f, Offset(hx + hw / 2, hy + hh / 2)) {
                    val hat = Path().apply {
                        moveTo(hx + hw * .04f, hy + hh * .86f)
                        quadraticTo(hx + hw * .28f, hy, hx + hw * .86f, hy + hh * .14f)
                        quadraticTo(hx + hw * .72f, hy + hh * .45f, hx + hw * .96f, hy + hh * .86f); close()
                    }
                    drawPath(hat, Brush.verticalGradient(listOf(Color(0xFFE8363F), Color(0xFFA5121B)), hy, hy + hh))
                    drawRoundRect(Color(0xFFFBF8F2), Offset(hx - hw * .02f, hy + hh * .76f), Size(hw * 1.04f, hh * .22f), CornerRadius(hh * .11f))
                    drawCircle(Color(0xFFFBF8F2), hw * .1f, Offset(hx + hw * .88f, hy + hh * .14f))
                }
            }
            if (th.deco == "halloween") {
                val sw = shellW * .07f; val sH = shellH * .2f
                rotate(10f, Offset(shellL + shellW / 2, shellT)) {
                    drawRoundRect(Brush.verticalGradient(listOf(Color(0xFF5E7D2E), Color(0xFF2F4417))), Offset(shellL + shellW / 2 - sw / 2, shellT - sH * .8f), Size(sw, sH), CornerRadius(sw * .35f))
                }
            }
        }
        // la faccia LED dentro il visore
        with(density) {
            val faceW = minOf(visW * .86f, visH * .8f * sh.cols / sh.rows)
            val faceH = faceW * sh.rows / sh.cols
            Box(Modifier.offset((visL + (visW - faceW) / 2).toDp(), (visT + (visH - faceH) / 2).toDp()).size(faceW.toDp(), faceH.toDp())) {
                DotFace(Modifier.fillMaxSize(), cols = sh.cols, rows = sh.rows)
            }
        }
    }
}
