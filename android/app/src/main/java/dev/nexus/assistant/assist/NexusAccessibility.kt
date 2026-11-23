package dev.nexus.assistant.assist

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume

/** Occhi e mani di NEXUS nelle altre app: legge lo schermo, tocca, scrive, scorre. */
class NexusAccessibility : AccessibilityService() {

    companion object {
        @Volatile var instance: NexusAccessibility? = null
        val enabled get() = instance != null
    }

    override fun onServiceConnected() { instance = this }
    override fun onDestroy() { instance = null; super.onDestroy() }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}

    data class Item(val text: String, val bounds: Rect, val clickable: Boolean, val editable: Boolean)

    private fun screenSize(): Pair<Int, Int> {
        val m = resources.displayMetrics
        return m.widthPixels to m.heightPixels
    }

    /** Tutti i testi visibili (anche dei pulsanti) con la loro posizione. */
    fun items(): List<Item> {
        val out = mutableListOf<Item>()
        fun walk(n: AccessibilityNodeInfo?, depth: Int) {
            if (n == null || depth > 40) return
            if (n.isVisibleToUser) {
                val t = (n.text ?: n.contentDescription ?: n.hintText)?.toString()?.trim().orEmpty()
                if (t.isNotEmpty() || n.isEditable) {
                    val r = Rect(); n.getBoundsInScreen(r)
                    if (r.width() > 0 && r.height() > 0) out += Item(t, r, n.isClickable, n.isEditable)
                }
            }
            for (i in 0 until n.childCount) walk(n.getChild(i), depth + 1)
        }
        val roots = windows?.mapNotNull { it.root }?.takeIf { it.isNotEmpty() } ?: listOfNotNull(rootInActiveWindow)
        roots.forEach { walk(it, 0) }
        return out
    }

    fun describeScreen(max: Int = 2500): String {
        val (w, h) = screenSize()
        val sb = StringBuilder()
        for (it in items()) {
            val cx = it.bounds.centerX() * 1000 / w; val cy = it.bounds.centerY() * 1000 / h
            val tag = if (it.editable) " (campo di testo)" else if (it.clickable) " (pulsante)" else ""
            sb.append("[$cx,$cy] ${it.text.replace('\n', ' ').take(80)}$tag\n")
            if (sb.length > max) break
        }
        return sb.toString().ifBlank { "(nessun testo leggibile sullo schermo)" }
    }

    private fun findNode(target: String): AccessibilityNodeInfo? {
        val t = target.lowercase().trim()
        var best: AccessibilityNodeInfo? = null; var bestScore = 0
        fun walk(n: AccessibilityNodeInfo?, depth: Int) {
            if (n == null || depth > 40) return
            if (n.isVisibleToUser) {
                val s = (n.text ?: n.contentDescription)?.toString()?.lowercase()?.trim().orEmpty()
                val score = when { s == t -> 100; s.startsWith(t) -> 80; s.contains(t) -> 60; t.contains(s) && s.length > 2 -> 40; else -> 0 }
                if (score > bestScore) { best = n; bestScore = score }
            }
            for (i in 0 until n.childCount) walk(n.getChild(i), depth + 1)
        }
        (windows?.mapNotNull { it.root } ?: listOfNotNull(rootInActiveWindow)).forEach { walk(it, 0) }
        return best
    }

    fun clickText(target: String): String? {
        val n = findNode(target) ?: return null
        var c: AccessibilityNodeInfo? = n
        while (c != null && !c.isClickable) c = c.parent
        if (c != null && c.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return (n.text ?: n.contentDescription).toString()
        val r = Rect(); n.getBoundsInScreen(r)
        tapPx(r.exactCenterX(), r.exactCenterY())
        return (n.text ?: n.contentDescription).toString()
    }

    private fun tapPx(x: Float, y: Float, long: Boolean = false) {
        val p = Path().apply { moveTo(x, y) }
        dispatchGesture(GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(p, 0, if (long) 700 else 60)).build(), null, null)
    }

    fun tap(nx: Float, ny: Float, long: Boolean = false) {
        val (w, h) = screenSize(); tapPx(nx / 1000f * w, ny / 1000f * h, long)
    }

    fun swipe(direction: String) {
        val (w, h) = screenSize()
        val (x1, y1, x2, y2) = when (direction) {
            "su" -> listOf(w * .5f, h * .75f, w * .5f, h * .25f)      // il contenuto va su (scorri in giù nella pagina)
            "giu" -> listOf(w * .5f, h * .25f, w * .5f, h * .75f)
            "sinistra" -> listOf(w * .85f, h * .5f, w * .15f, h * .5f)
            else -> listOf(w * .15f, h * .5f, w * .85f, h * .5f)
        }
        val p = Path().apply { moveTo(x1, y1); lineTo(x2, y2) }
        dispatchGesture(GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(p, 0, 350)).build(), null, null)
    }

    fun typeText(text: String, append: Boolean = false): Boolean {
        val root = rootInActiveWindow ?: return false
        var target = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        if (target == null || !target.isEditable) {
            fun firstEditable(n: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
                if (n == null) return null
                if (n.isEditable && n.isVisibleToUser) return n
                for (i in 0 until n.childCount) firstEditable(n.getChild(i))?.let { return it }
                return null
            }
            target = firstEditable(root)
        }
        target ?: return false
        target.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        val value = if (append) (target.text?.toString().orEmpty() + text) else text
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value) }
        return target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    fun global(action: String): Boolean = performGlobalAction(when (action) {
        "indietro" -> GLOBAL_ACTION_BACK
        "home" -> GLOBAL_ACTION_HOME
        "recenti" -> GLOBAL_ACTION_RECENTS
        "notifiche" -> GLOBAL_ACTION_NOTIFICATIONS
        "impostazioni_rapide" -> GLOBAL_ACTION_QUICK_SETTINGS
        "blocca" -> GLOBAL_ACTION_LOCK_SCREEN
        "screenshot" -> GLOBAL_ACTION_TAKE_SCREENSHOT
        else -> GLOBAL_ACTION_BACK
    })

    /** Screenshot (Android 11+) in JPEG base64, rimpicciolito per il modello. */
    suspend fun screenshotB64(maxW: Int = 720): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        return suspendCancellableCoroutine { cont ->
            takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, object : TakeScreenshotCallback {
                override fun onSuccess(result: ScreenshotResult) {
                    val hw = Bitmap.wrapHardwareBuffer(result.hardwareBuffer, result.colorSpace)
                    val bmp = hw?.copy(Bitmap.Config.ARGB_8888, false)
                    result.hardwareBuffer.close()
                    if (bmp == null) { cont.resume(null); return }
                    val scaled = if (bmp.width > maxW) Bitmap.createScaledBitmap(bmp, maxW, bmp.height * maxW / bmp.width, true) else bmp
                    val bos = ByteArrayOutputStream(); scaled.compress(Bitmap.CompressFormat.JPEG, 80, bos)
                    cont.resume(Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP))
                }
                override fun onFailure(errorCode: Int) { cont.resume(null) }
            })
        }
    }
}
