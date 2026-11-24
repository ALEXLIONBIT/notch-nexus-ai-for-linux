package dev.nexus.assistant.core

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.google.android.gms.tasks.Task
import com.google.android.gms.tasks.Tasks
import com.google.android.gms.wearable.MessageEvent
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import org.json.JSONArray
import org.json.JSONObject

/** Manda all'orologio (NEXUS per Wear OS) cervelli, aspetto e voce, tramite il Data Layer di Wear OS. */
object WatchSync {
    const val PATH = "/nexus/config"
    const val REQUEST = "/nexus/request"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var pending: Job? = null
    var status by mutableStateOf("")

    fun configJson(): String {
        val a = JSONArray(); Prefs.providers.forEach { a.put(it.toJson()) }
        return JSONObject().put("providers", a).put("activeProvider", Prefs.activeProvider).put("userName", Prefs.userName)
            .put("theme", Prefs.theme).put("led", Prefs.led).put("accent", Prefs.accent).put("shellCustom", Prefs.shellCustom)
            .put("bgCustom", Prefs.bgCustom).put("eyeStyle", Prefs.eyeStyle).put("mouthStyle", Prefs.mouthStyle)
            .put("dotShape", Prefs.dotShape).put("glow", Prefs.glow.toDouble()).put("customEye", Prefs.customEye)
            .put("customMouth", Prefs.customMouth).put("palette", Prefs.palette.joinToString(",") { (it.toLong() and 0xFFFFFFFFL).toString() })
            .put("speechRate", Prefs.speechRate.toDouble()).put("speechPitch", Prefs.speechPitch.toDouble())
            .put("autoMode", Prefs.autoMode).toString()
    }

    /** Dopo ogni salvataggio delle impostazioni (raggruppa i salvataggi ravvicinati). */
    fun schedule(ctx: Context) {
        val app = ctx.applicationContext
        pending?.cancel()
        pending = scope.launch { delay(1500); send(app, quiet = true) }
    }

    suspend fun send(ctx: Context, quiet: Boolean = false) {
        try {
            val nodes = Wearable.getNodeClient(ctx).connectedNodes.await()
            val req = PutDataMapRequest.create(PATH).apply {
                dataMap.putString("json", configJson())
                dataMap.putLong("t", System.currentTimeMillis())
            }.asPutDataRequest().setUrgent()
            Wearable.getDataClient(ctx).putDataItem(req).await()
            status = if (nodes.isEmpty()) "Nessun orologio collegato adesso: le impostazioni arriveranno quando si collega."
                     else "Inviato a ${nodes.joinToString { it.displayName }}"
        } catch (e: Exception) {
            if (!quiet) status = "Non riesco: ${e.message?.take(80)} (serve un orologio Wear OS abbinato)"
        }
    }
}

/** L'orologio chiede le impostazioni, oppure chiede al telefono di fare una richiesta al cervello per lui
 *  (quando l'orologio da solo non lo raggiunge, es. PC di casa via Tailscale). */
class PhoneWearService : WearableListenerService() {
    override fun onMessageReceived(e: MessageEvent) {
        if (e.path == WatchSync.REQUEST) CoroutineScope(Dispatchers.IO).launch { WatchSync.send(applicationContext, quiet = true) }
    }

    override fun onRequest(nodeId: String, path: String, request: ByteArray): Task<ByteArray>? {
        if (path != "/nexus/http") return null
        return Tasks.call(relayPool) {
            val out = JSONObject()
            try {
                val r = JSONObject(java.util.zip.GZIPInputStream(request.inputStream()).use { it.readBytes().decodeToString() })
                val b = Request.Builder().url(r.getString("url"))
                r.optString("key").takeIf { it.isNotBlank() }?.let { b.header("Authorization", "Bearer $it") }
                if (r.optString("method") == "POST") b.post(r.optString("body").toRequestBody("application/json".toMediaType()))
                relayHttp.newCall(b.build()).execute().use { resp -> out.put("code", resp.code).put("body", resp.body?.string().orEmpty()) }
            } catch (ex: Exception) { out.put("code", 0).put("error", ex.message ?: ex.toString()) }
            java.io.ByteArrayOutputStream().also { bo -> java.util.zip.GZIPOutputStream(bo).use { it.write(out.toString().toByteArray()) } }.toByteArray()
        }
    }

    companion object {
        private val relayPool = java.util.concurrent.Executors.newCachedThreadPool()
        private val relayHttp = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(180, TimeUnit.SECONDS).build()
    }
}
