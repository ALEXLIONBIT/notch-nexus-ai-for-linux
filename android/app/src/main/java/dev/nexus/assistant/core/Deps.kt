package dev.nexus.assistant.core

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/** Una cosa attorno all'app che può avere un aggiornamento: Ollama, i modelli, NEXUS sul PC, l'orologio. */
data class DepItem(
    val id: String,
    val name: String,
    val current: String = "",
    val latest: String = "",
    val state: String = "ok",          // ok | update | info | error
    val note: String = "",
    val action: String? = null,        // pc_models | direct_models | watch
    val base: String = "",
    val key: String = "",
    val models: List<String> = emptyList(),
)

/** "Controlla aggiornamenti" guarda anche quello che sta attorno al telefono:
 *  - il PC con NEXUS (gateway /nexus/status): versione di NEXUS, Ollama, modelli e programmi del PC;
 *  - un Ollama senza NEXUS: versione e modelli con una versione nuova su ollama.com;
 *  - l'orologio con NEXUS per Wear OS: versione installata e ultima uscita. */
object Deps {
    private const val OLLAMA_RELEASE = "https://api.github.com/repos/ollama/ollama/releases/latest"
    private const val RELEASES = "https://api.github.com/repos/ALEXLIONBIT/notch-nexus-ai-for-linux/releases?per_page=40"
    private const val REGISTRY = "https://registry.ollama.ai/v2"
    const val WATCH_VERSION = "/nexus/version"
    const val WATCH_UPDATE = "/nexus/update"

    var items by mutableStateOf(listOf<DepItem>())
    var checking by mutableStateOf(false)
    var working by mutableStateOf("")         // id della voce che si sta aggiornando
    var progress by mutableStateOf("")

    private val http = OkHttpClient.Builder().connectTimeout(8, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS).build()
    private val longHttp = http.newBuilder().readTimeout(0, TimeUnit.SECONDS).build()

    private fun req(url: String, key: String = "") = Request.Builder().url(url).header("User-Agent", "nexus-android")
        .apply { if (key.isNotBlank()) header("Authorization", "Bearer $key") }

    private fun get(url: String, key: String = ""): String = http.newCall(req(url, key).build()).execute().use { r ->
        val t = r.body?.string().orEmpty()
        if (!r.isSuccessful) throw java.io.IOException("HTTP ${r.code}")
        t
    }

    private fun ver(v: String) = Regex("\\d+").findAll(v).take(4).map { it.value.toInt() }.toList()
    private fun newer(a: String, b: String): Boolean {
        val x = ver(a); val y = ver(b)
        for (i in 0 until maxOf(x.size, y.size)) { val d = x.getOrElse(i) { 0 } - y.getOrElse(i) { 0 }; if (d != 0) return d > 0 }
        return false
    }

    private fun sha256(b: ByteArray) = MessageDigest.getInstance("SHA-256").digest(b).joinToString("") { "%02x".format(it) }

    /** Digest del modello su ollama.com; null se non viene da lì (creato in casa, hf.co…). */
    private fun registryDigest(name: String): String? {
        val base = name.substringBefore(":"); val tag = name.substringAfter(":", "latest")
        if (base.startsWith("hf.co/") || base.startsWith("huggingface.co/") || base.count { it == '/' } > 1) return null
        val ns = base.substringBeforeLast("/", "library"); val model = base.substringAfterLast("/")
        http.newCall(req("$REGISTRY/$ns/$model/manifests/$tag")
            .header("Accept", "application/vnd.docker.distribution.manifest.v2+json").build()).execute().use { r ->
            if (r.code == 404) return null
            if (!r.isSuccessful) throw java.io.IOException("HTTP ${r.code}")
            return sha256(r.body!!.bytes())
        }
    }

    private fun ollamaProviders() = Prefs.providers
        .filter { it.kind == "ollama" && !it.baseUrl.trimEnd('/').endsWith("/v1") && it.baseUrl.isNotBlank() }
        .distinctBy { it.baseUrl.trimEnd('/') }

    suspend fun check(ctx: Context) = withContext(Dispatchers.IO) {
        if (checking || working.isNotEmpty()) return@withContext
        checking = true
        try {
            val latestOllama = runCatching { JSONObject(get(OLLAMA_RELEASE)).getString("tag_name").removePrefix("v") }.getOrDefault("")
            val out = mutableListOf<DepItem>()
            for (p in ollamaProviders()) {
                val base = p.baseUrl.trimEnd('/')
                val pc = runCatching { JSONObject(get("$base/nexus/status", p.apiKey)) }.getOrNull()
                out += if (pc != null) fromPc(p, base, pc) else direct(p, base, latestOllama)
            }
            out += watch(ctx)
            items = out
        } finally { checking = false }
    }

    /** Il PC ha NEXUS: il controllo lo fa lui (anche i programmi del sistema), qui lo mostro. */
    private fun fromPc(p: Provider, base: String, pc: JSONObject): List<DepItem> {
        val out = mutableListOf<DepItem>()
        val who = p.name.ifBlank { "PC" }
        val nx = pc.optJSONObject("nexus") ?: JSONObject()
        val behind = nx.optInt("behind")
        out += DepItem("pc-nexus-$base", "NEXUS su $who", nx.optString("version").ifBlank { nx.optString("current") },
            if (behind > 0) "nuova versione" else "", if (behind > 0) "update" else "ok",
            if (behind > 0) "Si aggiorna dal PC: Personalizza → Aggiornamenti" else "")
        val deps = pc.optJSONObject("deps") ?: JSONObject()
        val arr = deps.optJSONArray("items") ?: JSONArray()
        if (arr.length() == 0 && deps.optBoolean("checking"))
            out += DepItem("pc-wait-$base", "$who: controllo in corso…", state = "info", note = "Riprova tra poco")
        for (i in 0 until arr.length()) {
            val d = arr.getJSONObject(i)
            val id = d.optString("id")
            val state = d.optString("state", "info")
            val remote = id == "models" && d.optString("action").let { it.isNotBlank() && it != "null" }
            var note = d.optString("note")
            if (deps.optString("working") == id && deps.optString("text").isNotBlank()) note = deps.optString("text")
            if (state == "update" && !remote) note = (if (note.isBlank()) "" else "$note · ") + "si aggiorna dal PC"
            val ms = d.optJSONArray("models")?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()
            out += DepItem("pc-$id-$base", "${d.optString("name")} ($who)", d.optString("current"), d.optString("latest"),
                state, note, if (remote) "pc_models" else null, base, p.apiKey, ms)
        }
        return out
    }

    /** Un Ollama senza NEXUS davanti: lo controllo da qui. */
    private suspend fun direct(p: Provider, base: String, latestOllama: String): List<DepItem> = coroutineScope {
        val who = p.name.ifBlank { "Ollama" }
        val out = mutableListOf<DepItem>()
        val v = runCatching { JSONObject(get("$base/api/version", p.apiKey)).optString("version") }.getOrNull()
        if (v == null) {
            out += DepItem("ollama-$base", "Ollama ($who)", state = "error", note = "Non risponde: il PC è acceso e collegato?")
            return@coroutineScope out
        }
        out += if (latestOllama.isNotBlank() && newer(latestOllama, v))
            DepItem("ollama-$base", "Ollama ($who)", v, latestOllama, "update", "Si aggiorna sul PC dove gira Ollama")
        else DepItem("ollama-$base", "Ollama ($who)", v)
        val tags = runCatching { JSONObject(get("$base/api/tags", p.apiKey)).getJSONArray("models") }.getOrNull()
        if (tags != null) {
            val list = (0 until tags.length()).map { tags.getJSONObject(it) }
            val old = list.map { m ->
                async(Dispatchers.IO) {
                    val d = runCatching { registryDigest(m.getString("name")) }.getOrNull()
                    if (d != null && d != m.optString("digest")) m.getString("name").removeSuffix(":latest") else null
                }
            }.awaitAll().filterNotNull()
            out += if (old.isEmpty()) DepItem("models-$base", "Modelli ($who)", "${list.size} installati")
            else DepItem("models-$base", "Modelli ($who)", "${list.size} installati", "${old.size} da aggiornare", "update",
                old.take(8).joinToString(", ") + if (old.size > 8) "…" else "", "direct_models", base, p.apiKey, old)
        }
        out
    }

    /** L'orologio: chiede la versione installata e la confronta con l'ultima release wear-v. */
    private suspend fun watch(ctx: Context): List<DepItem> {
        val nodes = runCatching { Wearable.getNodeClient(ctx).connectedNodes.await() }.getOrDefault(emptyList())
        if (nodes.isEmpty()) return emptyList()
        val latest = runCatching {
            val a = JSONArray(get(RELEASES))
            (0 until a.length()).map { a.getJSONObject(it) }
                .filter { it.optString("tag_name").startsWith("wear-v") && !it.optBoolean("draft") }
                .map { it.getString("tag_name").removePrefix("wear-v") }
                .reduceOrNull { x, y -> if (newer(y, x)) y else x }.orEmpty()
        }.getOrDefault("")
        return nodes.map { n ->
            val v = withTimeoutOrNull(8000) {
                runCatching { Wearable.getMessageClient(ctx).sendRequest(n.id, WATCH_VERSION, ByteArray(0)).await().decodeToString() }.getOrNull()
            }
            val name = "App dell'orologio (${n.displayName})"
            when {
                v == null -> DepItem("watch-${n.id}", name, state = "info",
                    note = "Non so che versione ha: sull'orologio apri NEXUS → Aggiornamenti", action = "watch", base = n.id)
                latest.isNotBlank() && newer(latest, v) -> DepItem("watch-${n.id}", name, v, latest, "update",
                    "La scarica l'orologio: conferma lì l'installazione", "watch", n.id)
                else -> DepItem("watch-${n.id}", name, v)
            }
        }
    }

    suspend fun apply(ctx: Context, item: DepItem) = withContext(Dispatchers.IO) {
        if (working.isNotEmpty()) return@withContext
        working = item.id; progress = ""
        try {
            when (item.action) {
                "pc_models" -> {
                    http.newCall(req("${item.base}/nexus/deps_apply", item.key)
                        .post("""{"id":"models"}""".toRequestBody("application/json".toMediaType())).build()).execute()
                        .use { if (!it.isSuccessful) error("il PC risponde HTTP ${it.code}") }
                    progress = "Il PC sta scaricando i modelli…"
                    delay(2000)
                    while (true) {                       // il lavoro lo fa il PC: qui seguo l'avanzamento
                        val d = runCatching { JSONObject(get("${item.base}/nexus/status", item.key)).getJSONObject("deps") }.getOrNull()
                        if (d != null) {
                            if (d.optString("working").isEmpty()) {
                                progress = d.optString("error").ifBlank { d.optString("text").ifBlank { "Fatto" } }
                                break
                            }
                            if (d.optString("text").isNotBlank()) progress = d.optString("text")
                        }
                        delay(3000)
                    }
                }
                "direct_models" -> {
                    for ((i, m) in item.models.withIndex()) {
                        progress = "[${i + 1}/${item.models.size}] $m…"
                        longHttp.newCall(req("${item.base}/api/pull", item.key)
                            .post(JSONObject().put("model", m).put("stream", true).toString().toRequestBody("application/json".toMediaType()))
                            .build()).execute().use { r ->
                            if (!r.isSuccessful) error("HTTP ${r.code}")
                            val src = r.body!!.source()
                            while (!src.exhausted()) {
                                val line = src.readUtf8Line() ?: break
                                val ev = runCatching { JSONObject(line) }.getOrNull() ?: continue
                                if (ev.has("error")) error(ev.getString("error"))
                                val tot = ev.optLong("total"); val done = ev.optLong("completed")
                                progress = "[${i + 1}/${item.models.size}] $m " + if (tot > 0) "${done * 100 / tot}%" else ev.optString("status")
                            }
                        }
                    }
                    progress = "Modelli aggiornati"
                }
                "watch" -> {
                    // apre NEXUS sull'orologio con nexus-wear://update: in primo piano può chiedere la conferma
                    val nodes = Wearable.getNodeClient(ctx).connectedNodes.await().filter { item.base.isBlank() || it.id == item.base }
                    val helper = androidx.wear.remote.interactions.RemoteActivityHelper(ctx)
                    for (n in nodes) {
                        val opened = runCatching {
                            helper.startRemoteActivity(android.content.Intent(android.content.Intent.ACTION_VIEW)
                                .addCategory(android.content.Intent.CATEGORY_BROWSABLE)
                                .setData(android.net.Uri.parse("nexus-wear://update")), n.id).get(20, TimeUnit.SECONDS)
                        }.isSuccess
                        if (!opened) Wearable.getMessageClient(ctx).sendMessage(n.id, WATCH_UPDATE, ByteArray(0)).await()
                    }
                    progress = "Guarda l'orologio: scarica l'aggiornamento e ti chiede di confermare"
                }
            }
        } catch (e: Exception) {
            progress = "Non riuscito: ${e.message?.take(100)}"
        } finally { working = "" }
        if (item.action != "watch") { val msg = progress; check(ctx); progress = msg }
    }
}
