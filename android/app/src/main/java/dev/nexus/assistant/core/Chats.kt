package dev.nexus.assistant.core

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/** Una chat nell'elenco. */
data class ChatInfo(val id: String, val title: String, val updated: Long, val count: Int, val preview: String)

/** Una chat salvata: le righe mostrate e la memoria del cervello (per riprendere il discorso). */
data class SavedChat(val id: String, val title: String, val created: Long, val lines: List<ChatLine>, val history: List<Msg>)

/** Chat salvate in filesDir/chats/<id>.json. */
object Chats {
    private fun dir(ctx: Context) = File(ctx.filesDir, "chats").apply { mkdirs() }

    fun newId(): String = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date()) + "-" + UUID.randomUUID().toString().take(4)

    fun title(text: String) = text.trim().replace(Regex("\\s+"), " ").let { if (it.length > 48) it.take(48) + "…" else it }

    private fun msgJson(m: Msg) = JSONObject().put("role", m.role).put("content", m.content).apply {
        m.toolCallId?.let { put("toolCallId", it) }
        m.name?.let { put("name", it) }
        if (m.toolCalls.isNotEmpty()) put("toolCalls", JSONArray().apply {
            m.toolCalls.forEach { put(JSONObject().put("id", it.id).put("name", it.name).put("args", it.args)) }
        })
    }

    private fun msgFrom(o: JSONObject) = Msg(
        role = o.optString("role"), content = o.optString("content"),
        toolCalls = o.optJSONArray("toolCalls")?.let { a ->
            (0 until a.length()).map { a.getJSONObject(it) }.map { ToolCall(it.optString("id"), it.optString("name"), it.optJSONObject("args") ?: JSONObject()) }
        } ?: emptyList(),
        toolCallId = o.optString("toolCallId").ifBlank { null }, name = o.optString("name").ifBlank { null },
    )

    fun save(ctx: Context, c: SavedChat) {
        if (c.lines.isEmpty()) return
        val o = JSONObject().put("id", c.id).put("title", c.title).put("created", c.created).put("updated", System.currentTimeMillis())
            .put("lines", JSONArray().apply { c.lines.forEach { l -> put(JSONObject().put("u", l.fromUser).put("t", l.text).apply { l.image?.let { put("img", it) } }) } })
            .put("history", JSONArray().apply { c.history.forEach { put(msgJson(it)) } })
        val f = File(dir(ctx), "${c.id}.json")
        val tmp = File(dir(ctx), "${c.id}.tmp")
        tmp.writeText(o.toString())
        tmp.renameTo(f)
    }

    fun load(ctx: Context, id: String): SavedChat? = runCatching {
        val o = JSONObject(File(dir(ctx), "$id.json").readText())
        val la = o.getJSONArray("lines")
        val ha = o.optJSONArray("history") ?: JSONArray()
        SavedChat(o.getString("id"), o.optString("title"), o.optLong("created"),
            (0 until la.length()).map { la.getJSONObject(it) }.map { ChatLine(it.optBoolean("u"), it.optString("t"), it.optString("img").ifBlank { null }) },
            (0 until ha.length()).map { msgFrom(ha.getJSONObject(it)) })
    }.getOrNull()

    fun delete(ctx: Context, id: String) { File(dir(ctx), "$id.json").delete() }

    /** Più recenti prima; con query cerca nel titolo e nei messaggi. */
    fun list(ctx: Context, query: String = ""): List<ChatInfo> {
        val q = query.trim().lowercase()
        return (dir(ctx).listFiles { f -> f.name.endsWith(".json") } ?: emptyArray()).mapNotNull { f ->
            runCatching {
                val o = JSONObject(f.readText())
                val la = o.getJSONArray("lines")
                if (la.length() == 0) return@runCatching null
                val texts = (0 until la.length()).map { la.getJSONObject(it).optString("t") }
                val title = o.optString("title").ifBlank { "Chat" }
                var preview = texts.last().replace('\n', ' ').take(90)
                if (q.isNotEmpty()) {
                    if (q !in title.lowercase()) {
                        val hit = texts.firstOrNull { q in it.lowercase() } ?: return@runCatching null
                        val i = hit.lowercase().indexOf(q); val s = maxOf(0, i - 25)
                        preview = (if (s > 0) "…" else "") + hit.substring(s, minOf(hit.length, i + 60)).replace('\n', ' ') + "…"
                    }
                }
                ChatInfo(o.getString("id"), title, o.optLong("updated"), la.length(), preview)
            }.getOrNull()
        }.sortedByDescending { it.updated }
    }

    fun whenText(t: Long): String {
        val d = Date(t); val now = Date()
        val day = SimpleDateFormat("yyyyMMdd", Locale.ITALIAN)
        val hm = SimpleDateFormat("HH:mm", Locale.ITALIAN).format(d)
        return when {
            day.format(d) == day.format(now) -> hm
            day.format(d) == day.format(Date(now.time - 86_400_000)) -> "ieri $hm"
            else -> SimpleDateFormat("d MMM", Locale.ITALIAN).format(d) + " " + hm
        }
    }
}
