package dev.nexus.assistant.wear

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import androidx.wear.remote.interactions.RemoteActivityHelper
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Collegare l'orologio a Tailscale: il login si apre sul telefono (o si inquadra il QR). */
object TsLogin {
    private var openedUrl = ""

    fun begin(ctx: Context, openOnPhone: Boolean = true) {
        Prefs.tailscale = true; Prefs.save()
        Ts.start(ctx.applicationContext, "nexus-orologio")
        if (!openOnPhone) return
        CoroutineScope(Dispatchers.Main).launch {
            repeat(60) {
                if (Ts.state == "Running") return@launch
                val url = Ts.authUrl
                if (url.isNotBlank() && url != openedUrl) { openedUrl = url; openOnPhone(ctx, url) }
                delay(1000)
            }
        }
    }

    fun openOnPhone(ctx: Context, url: String) {
        runCatching {
            RemoteActivityHelper(ctx.applicationContext).startRemoteActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)).addCategory(Intent.CATEGORY_BROWSABLE))
        }
    }

    fun qr(text: String, size: Int = 360): Bitmap {
        val m = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, size, size)
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        for (x in 0 until size) for (y in 0 until size) bmp.setPixel(x, y, if (m[x, y]) 0xFF000000.toInt() else 0xFFFFFFFF.toInt())
        return bmp
    }
}
