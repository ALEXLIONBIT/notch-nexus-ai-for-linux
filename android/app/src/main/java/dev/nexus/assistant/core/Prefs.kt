package dev.nexus.assistant.core

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** Un "cervello": Ollama (PC in casa, Tailscale, o sul telefono con Termux) oppure API compatibile OpenAI. */
data class Provider(
    val id: String = UUID.randomUUID().toString().take(8),
    val name: String,
    val preset: String,
    val kind: String,          // "ollama" | "openai"
    val baseUrl: String,
    val apiKey: String = "",
    val model: String,
) {
    fun toJson() = JSONObject().put("id", id).put("name", name).put("preset", preset).put("kind", kind)
        .put("baseUrl", baseUrl).put("apiKey", apiKey).put("model", model)

    companion object {
        fun from(o: JSONObject) = Provider(
            o.optString("id"), o.optString("name"), o.optString("preset"), o.optString("kind", "openai"),
            o.optString("baseUrl"), o.optString("apiKey"), o.optString("model"),
        )
    }
}

data class Preset(val key: String, val label: String, val kind: String, val baseUrl: String,
                  val model: String, val needsKey: Boolean, val hint: String = "")

val PRESETS = listOf(
    Preset("ollama", "Ollama su un PC (casa o Tailscale)", "ollama", "http://100.x.y.z:11434", "qwen3.5:4b", false,
        "Sul PC: Ollama in ascolto in rete (OLLAMA_HOST=0.0.0.0) oppure 'tailscale serve --tcp 11434 tcp://localhost:11434'."),
    Preset("openai", "OpenAI", "openai", "https://api.openai.com/v1", "gpt-4.1-mini", true),
    Preset("anthropic", "Anthropic (Claude)", "openai", "https://api.anthropic.com/v1/", "claude-haiku-5-5", true),
    Preset("gemini", "Google Gemini", "openai", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash", true),
    Preset("groq", "Groq", "openai", "https://api.groq.com/openai/v1", "meta-llama/llama-4-scout-17b-16e-instruct", true),
    Preset("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", "qwen/qwen3-vl-30b-a3b-instruct", true),
    Preset("lmstudio", "LM Studio / server OpenAI", "openai", "http://192.168.1.10:1234/v1", "", false),
    Preset("phone", "Sul telefono (Termux + Ollama, sconsigliato)", "ollama", "http://127.0.0.1:11434", "qwen3.5:2b", false,
        "Installa Termux, poi: pkg install ollama && ollama serve & ollama pull qwen3.5:2b. Lento e consuma batteria."),
)

/** Impostazioni osservabili da Compose e salvate subito. */
object Prefs {
    const val EYE_COLS = 9
    const val EYE_ROWS = 9
    const val MOUTH_COLS = 15
    const val MOUTH_ROWS = 5
    val DEFAULT_EYE = buildString {
        for (y in 0 until 9) for (x in 0 until 9) append(if ((x - 4) * (x - 4) + (y - 4) * (y - 4) <= 17) '1' else '0')
    }
    const val DEFAULT_MOUTH = "000000000000000" + "100000000000001" + "010000000000010" + "001110000011100" + "000001111100000"

    private lateinit var sp: SharedPreferences

    var providers by mutableStateOf(listOf<Provider>())
    var activeProvider by mutableStateOf("")
    var userName by mutableStateOf("")
    var imageUrl by mutableStateOf("")          // server immagini (NEXUS sul PC), es. http://100.x.y.z:11434

    // aspetto (stessi nomi del PC)
    var theme by mutableStateOf("grafite")
    var led by mutableStateOf(0xFF9BE7FF.toInt())
    var accent by mutableStateOf(0)            // 0 = come il principale
    var shellCustom by mutableStateOf(0)       // 0 = quello del tema
    var bgCustom by mutableStateOf(0)
    var eyeStyle by mutableStateOf("tondi")
    var mouthStyle by mutableStateOf("sorriso")
    var dotShape by mutableStateOf("tondi")
    var helmetShape by mutableStateOf("capsula")
    var antenna by mutableStateOf("nessuna")
    var ears by mutableStateOf(true)
    var glow by mutableStateOf(0.6f)
    var customEye by mutableStateOf(DEFAULT_EYE)
    var customMouth by mutableStateOf(DEFAULT_MOUTH)
    var palette by mutableStateOf(listOf(0xFFFF5A6E, 0xFFFFC861, 0xFF8CF5C8, 0xFFFF9FD8, 0xFFB9A6FF, 0xFFFFFFFF, 0xFF3DAEE9).map { it.toInt() })

    // voce
    var speechRate by mutableStateOf(1.05f)
    var speechPitch by mutableStateOf(0.85f)
    var autoListen by mutableStateOf(true)
    var autoMode by mutableStateOf(false)       // true = niente conferme
    var tailscale by mutableStateOf(false)      // Tailscale dentro NEXUS acceso

    private var appCtx: Context? = null

    fun init(ctx: Context) {
        appCtx = ctx.applicationContext
        sp = ctx.getSharedPreferences("nexus", Context.MODE_PRIVATE)
        providers = runCatching {
            val a = JSONArray(sp.getString("providers", "[]"))
            (0 until a.length()).map { Provider.from(a.getJSONObject(it)) }
        }.getOrDefault(emptyList())
        activeProvider = sp.getString("activeProvider", "") ?: ""
        userName = sp.getString("userName", "") ?: ""
        imageUrl = sp.getString("imageUrl", "") ?: ""
        theme = sp.getString("theme", theme)!!
        led = sp.getInt("led", led); accent = sp.getInt("accent", 0)
        shellCustom = sp.getInt("shellCustom", 0); bgCustom = sp.getInt("bgCustom", 0)
        eyeStyle = sp.getString("eyeStyle", eyeStyle)!!; mouthStyle = sp.getString("mouthStyle", mouthStyle)!!
        dotShape = sp.getString("dotShape", dotShape)!!; helmetShape = sp.getString("helmetShape", helmetShape)!!
        antenna = sp.getString("antenna", antenna)!!; ears = sp.getBoolean("ears", true)
        glow = sp.getFloat("glow", 0.6f)
        customEye = sp.getString("customEye", DEFAULT_EYE)!!; customMouth = sp.getString("customMouth", DEFAULT_MOUTH)!!
        sp.getString("palette", null)?.let { s -> palette = s.split(",").mapNotNull { it.toLongOrNull()?.toInt() } }
        speechRate = sp.getFloat("speechRate", 1.05f); speechPitch = sp.getFloat("speechPitch", 0.85f)
        autoListen = sp.getBoolean("autoListen", true)
        autoMode = sp.getBoolean("autoMode", false)
        tailscale = sp.getBoolean("tailscale", false)
    }

    fun save() {
        val a = JSONArray(); providers.forEach { a.put(it.toJson()) }
        sp.edit()
            .putString("providers", a.toString()).putString("activeProvider", activeProvider)
            .putString("userName", userName).putString("imageUrl", imageUrl).putString("theme", theme)
            .putInt("led", led).putInt("accent", accent).putInt("shellCustom", shellCustom).putInt("bgCustom", bgCustom)
            .putString("eyeStyle", eyeStyle).putString("mouthStyle", mouthStyle).putString("dotShape", dotShape)
            .putString("helmetShape", helmetShape).putString("antenna", antenna).putBoolean("ears", ears)
            .putFloat("glow", glow).putString("customEye", customEye).putString("customMouth", customMouth)
            .putString("palette", palette.joinToString(",") { (it.toLong() and 0xFFFFFFFFL).toString() })
            .putFloat("speechRate", speechRate).putFloat("speechPitch", speechPitch).putBoolean("autoListen", autoListen).putBoolean("autoMode", autoMode).putBoolean("tailscale", tailscale)
            .apply()
        appCtx?.let { WatchSync.schedule(it) }        // anche l'orologio resta aggiornato
    }

    fun active(): Provider? = providers.firstOrNull { it.id == activeProvider } ?: providers.firstOrNull()

    fun upsert(p: Provider, select: Boolean) {
        val old = providers.firstOrNull { it.id == p.id }
        val fixed = if (old != null && p.apiKey.isBlank()) p.copy(apiKey = old.apiKey) else p
        providers = if (old != null) providers.map { if (it.id == p.id) fixed else it } else providers + fixed
        if (select || activeProvider.isBlank()) activeProvider = fixed.id
        save()
    }

    fun remove(id: String) {
        providers = providers.filterNot { it.id == id }
        if (activeProvider == id) activeProvider = providers.firstOrNull()?.id ?: ""
        save()
    }

    fun paletteColor(i: Int): Int = if (i <= 1) led else palette.getOrElse(i - 2) { led }

}
