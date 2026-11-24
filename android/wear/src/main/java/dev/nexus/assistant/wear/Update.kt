package dev.nexus.assistant.wear

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.util.concurrent.TimeUnit

/** Aggiornamenti dalle release GitHub "wear-vX.Y.Z": scarica l'APK e lo installa (Android chiede conferma). */
object Update {
    private const val API = "https://api.github.com/repos/ALEXLIONBIT/notch-nexus-ai-for-linux/releases?per_page=30"
    var status by mutableStateOf("")
    var busy by mutableStateOf(false)
    private val http = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS).build()

    private fun ver(s: String) = s.removePrefix("wear-v").split(".").map { it.toIntOrNull() ?: 0 }
    private fun newer(a: List<Int>, b: List<Int>): Boolean {
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }; val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    suspend fun check(ctx: Context) = withContext(Dispatchers.IO) {
        if (busy) return@withContext
        busy = true
        try {
            status = "Controllo…"
            val mine = ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "0"
            val arr = http.newCall(Request.Builder().url(API).header("Accept", "application/vnd.github+json").build()).execute()
                .use { JSONArray(it.body!!.string()) }
            var best: Pair<String, String>? = null      // tag, url apk
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                val tag = r.optString("tag_name")
                if (!tag.startsWith("wear-v") || r.optBoolean("draft") || r.optBoolean("prerelease")) continue
                val assets = r.optJSONArray("assets") ?: continue
                val apk = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull { it.optString("name").endsWith(".apk") } ?: continue
                if (best == null || newer(ver(tag), ver(best.first))) best = tag to apk.optString("browser_download_url")
            }
            val b = best
            if (b == null || !newer(ver(b.first), ver(mine))) { status = "Già aggiornato ($mine)"; return@withContext }
            status = "Scarico ${b.first.removePrefix("wear-")}…"
            val inst = ctx.packageManager.packageInstaller
            val id = inst.createSession(PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL))
            inst.openSession(id).use { s ->
                http.newCall(Request.Builder().url(b.second).build()).execute().use { resp ->
                    val body = resp.body ?: error("download vuoto")
                    s.openWrite("nexus.apk", 0, body.contentLength()).use { out -> body.byteStream().copyTo(out); s.fsync(out) }
                }
                val pi = PendingIntent.getBroadcast(ctx, id, Intent(ctx, UpdateReceiver::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
                status = "Installo…"
                s.commit(pi.intentSender)
            }
        } catch (e: Exception) {
            status = "Errore: ${e.message ?: e}"
        } finally { busy = false }
    }
}

class UpdateReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -999)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT) ?: return
                ctx.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                Update.status = "Conferma l'installazione"
            }
            PackageInstaller.STATUS_SUCCESS -> Update.status = "Aggiornato"
            else -> Update.status = "Non installato: " + (intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "annullato")
        }
    }
}
