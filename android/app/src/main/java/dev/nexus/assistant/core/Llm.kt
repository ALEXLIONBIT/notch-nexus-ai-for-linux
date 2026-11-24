package dev.nexus.assistant.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class ToolCall(val id: String, val name: String, val args: JSONObject)

/** Messaggio neutro: viene convertito nel formato di Ollama o di OpenAI. */
data class Msg(
    val role: String,
    val content: String = "",
    val imageB64: String? = null,
    val toolCalls: List<ToolCall> = emptyList(),
    val toolCallId: String? = null,
    val name: String? = null,
)

object Llm {
    private val http = OkHttpClient.Builder().proxySelector(Ts.selector)
        .connectTimeout(15, TimeUnit.SECONDS).readTimeout(180, TimeUnit.SECONDS).build()
    private val JSON_TYPE = "application/json".toMediaType()

    private suspend fun Call.await(): Response = suspendCancellableCoroutine { cont ->
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { if (cont.isActive) cont.resumeWithException(e) }
            override fun onResponse(call: Call, response: Response) { cont.resume(response) }
        })
        cont.invokeOnCancellation { runCatching { cancel() } }
    }

    private suspend fun post(url: String, body: JSONObject, key: String): JSONObject = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url).post(body.toString().toRequestBody(JSON_TYPE))
        if (key.isNotBlank()) req.header("Authorization", "Bearer $key")
        http.newCall(req.build()).await().use { r ->
            val txt = r.body?.string().orEmpty()
            if (!r.isSuccessful) throw IOException("HTTP ${r.code}: ${txt.take(200)}")
            JSONObject(txt)
        }
    }

    private suspend fun get(url: String, key: String): JSONObject = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(url)
        if (key.isNotBlank()) req.header("Authorization", "Bearer $key")
        http.newCall(req.build()).await().use { r ->
            val txt = r.body?.string().orEmpty()
            if (!r.isSuccessful) throw IOException("HTTP ${r.code}: ${txt.take(200)}")
            JSONObject(txt)
        }
    }

    private fun base(p: Provider) = p.baseUrl.trimEnd('/')

    /** Un indirizzo che finisce con /v1 è un'API in stile OpenAI anche se salvato come "Ollama". */
    private fun isOllama(p: Provider) = p.kind == "ollama" && !p.baseUrl.trimEnd('/').endsWith("/v1")

    /** Contesto dell'app: serve per i modelli che girano sul dispositivo (llama.cpp). */
    lateinit var appContext: android.content.Context

    suspend fun chat(p: Provider, msgs: List<Msg>, tools: JSONArray): Pair<String, List<ToolCall>> =
        if (p.kind == "device") deviceChat(p, msgs, tools)
        else if (isOllama(p)) ollamaChat(p, msgs, tools) else openaiChat(p, msgs, tools)

    suspend fun models(p: Provider): List<String> =
        if (p.kind == "device") dev.nexus.llama.LocalLlm.installed(appContext).map { it.name }
        else if (isOllama(p)) {
            val a = get("${base(p)}/api/tags", p.apiKey).getJSONArray("models")
            (0 until a.length()).map { a.getJSONObject(it).getString("name") }.sorted()
        } else {
            val a = get("${base(p)}/models", p.apiKey).getJSONArray("data")
            (0 until a.length()).map { a.getJSONObject(it).getString("id") }.sorted()
        }

    // ------------------------------------------------------------ Ollama
    private suspend fun ollamaChat(p: Provider, msgs: List<Msg>, tools: JSONArray): Pair<String, List<ToolCall>> {
        val arr = JSONArray()
        for (m in msgs) {
            val o = JSONObject().put("role", m.role).put("content", m.content)
            if (m.imageB64 != null) o.put("images", JSONArray().put(m.imageB64))
            if (m.toolCalls.isNotEmpty()) o.put("tool_calls", JSONArray().apply {
                m.toolCalls.forEach { put(JSONObject().put("function", JSONObject().put("name", it.name).put("arguments", it.args))) }
            })
            if (m.role == "tool") o.put("tool_name", m.name ?: "")
            arr.put(o)
        }
        val body = JSONObject().put("model", p.model).put("messages", arr).put("stream", false).put("think", false)
            .put("keep_alive", "30m").put("options", JSONObject().put("num_ctx", 16384).put("temperature", 0.3))
        if (tools.length() > 0) body.put("tools", tools)
        val r = try { post("${base(p)}/api/chat", body, p.apiKey) } catch (e: IOException) {
            if (e.message?.contains("think") == true) post("${base(p)}/api/chat", body.apply { remove("think") }, p.apiKey) else throw e
        }
        val msg = r.getJSONObject("message")
        val calls = mutableListOf<ToolCall>()
        msg.optJSONArray("tool_calls")?.let { a ->
            for (i in 0 until a.length()) {
                val f = a.getJSONObject(i).getJSONObject("function")
                val args = f.opt("arguments").let { if (it is JSONObject) it else runCatching { JSONObject(it.toString()) }.getOrDefault(JSONObject()) }
                calls += ToolCall("call_" + UUID.randomUUID().toString().take(8), f.getString("name"), args)
            }
        }
        return msg.optString("content", "") to calls
    }

    // ------------------------------------------------------------ OpenAI-compatibile
    // ------------------------------------------------------------ sul dispositivo (llama.cpp)
    private suspend fun deviceChat(p: Provider, msgs: List<Msg>, tools: JSONArray): Pair<String, List<ToolCall>> =
        withContext(Dispatchers.Default) {
            parseOpenAi(dev.nexus.llama.LocalLlm.chat(appContext, p.model, toOpenAi(forDevice(msgs)), tools))
        }

    private val nowLine = Regex("\\s*Data e ora: [^\\n]*$")

    /**
     * Per i modelli sul dispositivo: niente immagini, e data/ora spostate dal prompt di sistema all'ultima domanda.
     * Così il prompt di sistema con gli strumenti resta identico e il modello non lo ricalcola a ogni minuto.
     */
    private fun forDevice(msgs: List<Msg>): List<Msg> {
        val out = msgs.map { it.copy(imageB64 = null) }.toMutableList()
        val sys = out.firstOrNull()?.takeIf { it.role == "system" } ?: return out
        val m = nowLine.find(sys.content) ?: return out
        out[0] = sys.copy(content = sys.content.removeRange(m.range))
        val last = out.indexOfLast { it.role == "user" }
        if (last >= 0) out[last] = out[last].copy(content = out[last].content + "\n(" + m.value.trim() + ")")
        return out
    }

    /** Prepara il modello sul dispositivo (prompt di sistema + strumenti già calcolati): la prima domanda è veloce. */
    suspend fun warmup(p: Provider, system: String, tools: JSONArray) {
        if (p.kind != "device") return
        withContext(Dispatchers.Default) {
            runCatching {
                dev.nexus.llama.LocalLlm.chat(appContext, p.model, toOpenAi(forDevice(listOf(Msg("system", system), Msg("user", "ciao")))), tools, maxTokens = 1)
            }
        }
    }

    private fun parseOpenAi(msg: JSONObject): Pair<String, List<ToolCall>> {
        val calls = mutableListOf<ToolCall>()
        msg.optJSONArray("tool_calls")?.let { a ->
            for (i in 0 until a.length()) {
                val c = a.getJSONObject(i); val f = c.getJSONObject("function")
                val args = runCatching { JSONObject(f.optString("arguments", "{}").ifBlank { "{}" }) }.getOrDefault(JSONObject())
                calls += ToolCall(c.optString("id").ifBlank { "call_" + UUID.randomUUID().toString().take(8) }, f.getString("name"), args)
            }
        }
        return (if (msg.isNull("content")) "" else msg.optString("content", "")) to calls
    }

    private fun toOpenAi(msgs: List<Msg>): JSONArray {
        val arr = JSONArray()
        for (m in msgs) {
            val o = JSONObject().put("role", m.role)
            when {
                m.role == "tool" -> o.put("tool_call_id", m.toolCallId ?: "").put("content", m.content)
                m.toolCalls.isNotEmpty() -> {
                    o.put("content", m.content)
                    o.put("tool_calls", JSONArray().apply {
                        m.toolCalls.forEach {
                            put(JSONObject().put("id", it.id).put("type", "function")
                                .put("function", JSONObject().put("name", it.name).put("arguments", it.args.toString())))
                        }
                    })
                }
                m.imageB64 != null -> o.put("content", JSONArray()
                    .put(JSONObject().put("type", "text").put("text", m.content))
                    .put(JSONObject().put("type", "image_url").put("image_url", JSONObject().put("url", "data:image/jpeg;base64,${m.imageB64}"))))
                else -> o.put("content", m.content)
            }
            arr.put(o)
        }
        return arr
    }

    private suspend fun openaiChat(p: Provider, msgs: List<Msg>, tools: JSONArray): Pair<String, List<ToolCall>> {
        val arr = toOpenAi(msgs)
        val body = JSONObject().put("model", p.model).put("messages", arr).put("temperature", 0.3)
        if (tools.length() > 0) body.put("tools", tools)
        val r = post("${base(p)}/chat/completions", body, p.apiKey)
        val msg = r.getJSONArray("choices").getJSONObject(0).getJSONObject("message")
        val calls = mutableListOf<ToolCall>()
        msg.optJSONArray("tool_calls")?.let { a ->
            for (i in 0 until a.length()) {
                val c = a.getJSONObject(i); val f = c.getJSONObject("function")
                val args = runCatching { JSONObject(f.optString("arguments", "{}").ifBlank { "{}" }) }.getOrDefault(JSONObject())
                calls += ToolCall(c.optString("id").ifBlank { "call_" + UUID.randomUUID().toString().take(8) }, f.getString("name"), args)
            }
        }
        return (if (msg.isNull("content")) "" else msg.optString("content", "")) to calls
    }
}
