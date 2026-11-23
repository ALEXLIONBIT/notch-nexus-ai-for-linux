package dev.nexus.assistant.core

import android.content.Context
import android.content.Intent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.io.File

/** Aggiornamenti dell'app: controlla le release su GitHub, scarica l'APK nuovo e apre l'installazione. */
object Updater {
    private const val API = "https://api.github.com/repos/ALEXLIONBIT/notch-nexus-ai-for-linux/releases"
    private val http = OkHttpClient()

    var latest by mutableStateOf("")        // es. "0.2.0" se c'è una versione più nuova
    var apkUrl by mutableStateOf("")
    var status by mutableStateOf("")
    var busy by mutableStateOf(false)

    fun current(ctx: Context): String =
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "0"

    private fun newer(a: String, b: String): Boolean {
        val x = a.split(".").map { it.toIntOrNull() ?: 0 }; val y = b.split(".").map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) { val d = x.getOrElse(i) { 0 } - y.getOrElse(i) { 0 }; if (d != 0) return d > 0 }
        return false
    }

    suspend fun check(ctx: Context) = withContext(Dispatchers.IO) {
        busy = true; status = "Controllo…"
        try {
            val body = http.newCall(Request.Builder().url(API).header("User-Agent", "nexus-android").build()).execute()
                .use { it.body?.string().orEmpty() }
            val arr = JSONArray(body)
            var bestV = ""; var bestUrl = ""
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                val tag = r.optString("tag_name")
                if (!tag.startsWith("android-v") || r.optBoolean("draft")) continue
                val v = tag.removePrefix("android-v")
                val assets = r.getJSONArray("assets")
                val apk = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull { it.optString("name").endsWith(".apk") } ?: continue
                if (bestV.isEmpty() || newer(v, bestV)) { bestV = v; bestUrl = apk.getString("browser_download_url") }
            }
            if (bestV.isNotEmpty() && newer(bestV, current(ctx))) { latest = bestV; apkUrl = bestUrl; status = "Disponibile la versione $bestV" }
            else { latest = ""; status = "Hai già l'ultima versione (${current(ctx)})" }
        } catch (e: Exception) { status = "Non riesco a controllare: ${e.message?.take(80)}" }
        busy = false
    }

    suspend fun downloadAndInstall(ctx: Context) {
        if (apkUrl.isBlank()) return
        busy = true; status = "Scarico la versione $latest…"
        try {
            val file = withContext(Dispatchers.IO) {
                val f = File(ctx.cacheDir, "updates/nexus-$latest.apk").apply { parentFile?.mkdirs() }
                http.newCall(Request.Builder().url(apkUrl).build()).execute().use { r ->
                    if (!r.isSuccessful) error("HTTP ${r.code}")
                    f.outputStream().use { out -> r.body!!.byteStream().copyTo(out) }
                }
                f
            }
            val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", file)
            ctx.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
            status = "Conferma l'installazione"
        } catch (e: Exception) { status = "Download non riuscito: ${e.message?.take(80)}" }
        busy = false
    }
}
