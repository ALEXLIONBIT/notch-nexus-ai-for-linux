package dev.nexus.llama

import android.app.ActivityManager
import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/** Ponte verso la libreria nativa (llama.cpp). */
object LlamaNative {
    fun interface TokenListener { fun onToken(piece: String): Boolean }

    @Volatile private var ready = false

    fun ensure(ctx: Context) {
        if (ready) return
        synchronized(this) {
            if (ready) return
            try { System.loadLibrary("nexusllama") } catch (e: UnsatisfiedLinkError) {
                val abi = android.os.Build.SUPPORTED_ABIS.joinToString(",")
                error("libreria dei modelli non caricata (abi $abi, ${if (android.os.Process.is64Bit()) "64" else "32"} bit): ${e.message?.take(80)}")
            }
            init(ctx.applicationInfo.nativeLibraryDir)
            ready = true
        }
    }

    external fun init(libDir: String)
    external fun load(path: String, nCtx: Int, nThreads: Int): String
    external fun unload()
    external fun cancel()
    external fun chat(messagesJson: String, toolsJson: String, maxTokens: Int, temp: Float, thinking: Boolean,
                      listener: TokenListener?): String
}

/** Un modello GGUF consigliato: repo e file su Hugging Face. */
data class CatalogModel(val name: String, val repo: String, val file: String, val sizeMb: Int,
                        val note: String, val watch: Boolean)

/** Un file GGUF trovato con la ricerca su Hugging Face. */
data class HfFile(val repo: String, val file: String, val sizeMb: Int, val downloads: Int)

/**
 * Modelli AI che girano sul dispositivo (telefono o orologio): catalogo, ricerca su Hugging Face,
 * download (riprende se si interrompe), caricamento e chat con strumenti nel formato OpenAI.
 */
object LocalLlm {
    val CATALOG = listOf(
        CatalogModel("Gemma 3 270M", "unsloth/gemma-3-270m-it-GGUF", "gemma-3-270m-it-Q8_0.gguf", 278,
            "Piccolissimo: risponde in fretta anche sull'orologio, ma capisce poco", true),
        CatalogModel("Qwen 2.5 0.5B", "Qwen/Qwen2.5-0.5B-Instruct-GGUF", "qwen2.5-0.5b-instruct-q4_k_m.gguf", 468,
            "Il più adatto all'orologio: usa anche gli strumenti", true),
        CatalogModel("Qwen 3 0.6B", "unsloth/Qwen3-0.6B-GGUF", "Qwen3-0.6B-Q4_K_M.gguf", 378,
            "Simile, un po' più sveglio, a volte più lento", true),
        CatalogModel("Gemma 3 1B", "unsloth/gemma-3-1b-it-GGUF", "gemma-3-1b-it-Q4_K_M.gguf", 768,
            "Buon italiano; sull'orologio solo se ha 2 GB di RAM", true),
        CatalogModel("Llama 3.2 1B", "unsloth/Llama-3.2-1B-Instruct-GGUF", "Llama-3.2-1B-Instruct-Q4_K_M.gguf", 770,
            "Veloce sul telefono, usa gli strumenti", false),
        CatalogModel("Qwen 2.5 1.5B", "Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf", 1065,
            "Il miglior equilibrio sul telefono", false),
        CatalogModel("Qwen 3 1.7B", "unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf", 1056,
            "Telefono: ragiona meglio, strumenti affidabili", false),
        CatalogModel("Gemma 3 4B", "unsloth/gemma-3-4b-it-GGUF", "gemma-3-4b-it-Q4_K_M.gguf", 2374,
            "Telefoni con 8 GB o più: il più intelligente", false),
        CatalogModel("Qwen 3 4B", "unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", 2381,
            "Telefoni con 8 GB o più: ottimo con gli strumenti", false),
    )

    private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS)
        .followRedirects(true).build()

    fun dir(ctx: Context) = File(ctx.filesDir, "models").apply { mkdirs() }

    /** Modelli già scaricati (file .gguf completi). */
    fun installed(ctx: Context): List<File> =
        dir(ctx).listFiles { f -> f.name.endsWith(".gguf") }?.sortedBy { it.length() } ?: emptyList()

    fun fileFor(ctx: Context, name: String) = File(dir(ctx), name)

    fun delete(ctx: Context, name: String) {
        if (loaded == name) unload()
        fileFor(ctx, name).delete()
        File(dir(ctx), "$name.part").delete()
    }

    /** RAM totale del dispositivo in MB (per consigliare cosa ci sta). */
    fun ramMb(ctx: Context): Int {
        val mi = ActivityManager.MemoryInfo()
        (ctx.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(mi)
        return (mi.totalMem / (1024 * 1024)).toInt()
    }

    /** Ci sta in memoria? (pesi + cache + margine per il sistema) */
    fun fits(ctx: Context, sizeMb: Int) = sizeMb * 1.6 + 600 < ramMb(ctx) * 0.75

    /** Cerca modelli GGUF su Hugging Face; per ogni repo propone il file Q4_K_M (o il più simile). */
    fun search(query: String, limit: Int = 12): List<HfFile> {
        val q = URLEncoder.encode(query.trim(), "UTF-8")
        val url = "https://huggingface.co/api/models?search=$q&filter=gguf&sort=downloads&direction=-1&limit=$limit"
        val repos = http.newCall(Request.Builder().url(url).build()).execute().use { JSONArray(it.body!!.string()) }
        val out = mutableListOf<HfFile>()
        for (i in 0 until repos.length()) {
            val r = repos.getJSONObject(i)
            val id = r.optString("id")
            runCatching { pickFile(id) }.getOrNull()?.let { (f, size) -> out += HfFile(id, f, size, r.optInt("downloads")) }
        }
        return out
    }

    private val PREF = listOf("q4_k_m", "q4_0", "q4_k_s", "iq4_xs", "q5_k_m", "q8_0")

    private fun pickFile(repo: String): Pair<String, Int>? {
        val tree = http.newCall(Request.Builder().url("https://huggingface.co/api/models/$repo/tree/main").build())
            .execute().use { JSONArray(it.body!!.string()) }
        val files = (0 until tree.length()).map { tree.getJSONObject(it) }
            .filter { it.optString("path").endsWith(".gguf") && "mmproj" !in it.optString("path").lowercase() }
        val best = files.minByOrNull { f -> PREF.indexOfFirst { it in f.optString("path").lowercase() }.let { if (it < 0) 99 else it } }
            ?: return null
        val size = (best.optJSONObject("lfs")?.optLong("size") ?: best.optLong("size")) / (1024 * 1024)
        return best.optString("path") to size.toInt()
    }

    /** Scarica un file GGUF (riprende da dove si era fermato). progress(MB scaricati, MB totali). */
    fun download(ctx: Context, repo: String, file: String, progress: (Int, Int) -> Unit, cancelled: () -> Boolean = { false }): File {
        val name = file.substringAfterLast('/')
        val dest = fileFor(ctx, name)
        if (dest.exists()) return dest
        val part = File(dir(ctx), "$name.part")
        val have = if (part.exists()) part.length() else 0L
        val req = Request.Builder().url("https://huggingface.co/$repo/resolve/main/$file?download=true")
            .apply { if (have > 0) header("Range", "bytes=$have-") }.build()
        http.newBuilder().readTimeout(120, TimeUnit.SECONDS).build().newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) error("download non riuscito (${resp.code})")
            val body = resp.body ?: error("download vuoto")
            val resumed = resp.code == 206
            val total = (if (resumed) have else 0L) + body.contentLength()
            RandomAccessFile(part, "rw").use { out ->
                if (resumed) out.seek(have) else out.setLength(0)
                var done = if (resumed) have else 0L
                val buf = ByteArray(1 shl 16)
                val input = body.byteStream()
                var lastMb = -1
                while (true) {
                    if (cancelled()) error("download annullato")
                    val n = input.read(buf)
                    if (n < 0) break
                    out.write(buf, 0, n)
                    done += n
                    val mb = (done / (1024 * 1024)).toInt()
                    if (mb != lastMb) { lastMb = mb; progress(mb, (total / (1024 * 1024)).toInt()) }
                }
            }
        }
        if (!part.renameTo(dest)) error("non riesco a salvare il modello")
        return dest
    }

    // ------------------------------------------------------------ esecuzione
    @Volatile var loaded: String? = null
        private set

    /** Carica il modello (se non è già quello caricato). Contesto più piccolo sui dispositivi con poca RAM. */
    @Synchronized
    fun load(ctx: Context, name: String) {
        if (loaded == name) return
        LlamaNative.ensure(ctx)
        val f = fileFor(ctx, name)
        if (!f.exists()) error("il modello $name non è sul dispositivo")
        val ram = ramMb(ctx)
        // la cache costa poco per i modelli piccoli: 4096 token anche sull'orologio (servono per gli strumenti)
        val nCtx = if (ram < 3000 && f.length() > 700L * 1024 * 1024) 2048 else 4096
        val cores = Runtime.getRuntime().availableProcessors()
        val threads = (cores - if (cores > 4) 2 else 1).coerceIn(1, 6)
        val err = LlamaNative.load(f.path, nCtx, threads)
        if (err.isNotEmpty()) { loaded = null; error(err) }
        loaded = name
    }

    @Synchronized
    fun unload() { runCatching { LlamaNative.unload() }; loaded = null }

    fun cancel() = runCatching { LlamaNative.cancel() }

    /**
     * Chat in formato OpenAI: messages e tools come gli array di /chat/completions.
     * Ritorna il messaggio dell'assistente (content, tool_calls…) come JSONObject.
     */
    fun chat(ctx: Context, model: String, messages: JSONArray, tools: JSONArray, maxTokens: Int = 512,
             onToken: ((String) -> Boolean)? = null): JSONObject {
        load(ctx, model)
        val r = JSONObject(LlamaNative.chat(messages.toString(), tools.toString(), maxTokens, 0.3f, false,
            onToken?.let { f -> LlamaNative.TokenListener { f(it) } }))
        if (r.has("error")) error(r.getString("error"))
        return r
    }
}
