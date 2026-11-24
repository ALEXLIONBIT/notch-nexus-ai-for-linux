package dev.nexus.whisper

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

/** whisper.cpp: trascrive frasi brevi sul dispositivo (per sentire il nome dell'agente). */
object WhisperNative {
    private const val MODEL = "ggml-base-q5_1.bin"
    private const val URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL"

    @Volatile private var loaded = false

    external fun load(path: String): Boolean
    external fun free()
    external fun transcribe(pcm: FloatArray, lang: String, prompt: String, threads: Int): String

    fun modelFile(ctx: Context) = File(File(ctx.filesDir, "models").apply { mkdirs() }, MODEL)

    fun ready(ctx: Context) = modelFile(ctx).exists()

    /** Scarica il modello (circa 57 MB) se manca. progress(MB, MB totali). */
    fun download(ctx: Context, progress: (Int, Int) -> Unit = { _, _ -> }) {
        val dest = modelFile(ctx)
        if (dest.exists()) return
        val part = File(dest.path + ".part")
        val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).build()
        http.newCall(Request.Builder().url(URL).build()).execute().use { r ->
            if (!r.isSuccessful) error("download del modello vocale non riuscito (${r.code})")
            val body = r.body ?: error("download vuoto")
            val total = (body.contentLength() / (1024 * 1024)).toInt()
            part.outputStream().use { out ->
                val buf = ByteArray(1 shl 16); var done = 0L; var last = -1
                val input = body.byteStream()
                while (true) {
                    val n = input.read(buf); if (n < 0) break
                    out.write(buf, 0, n); done += n
                    val mb = (done / (1024 * 1024)).toInt(); if (mb != last) { last = mb; progress(mb, total) }
                }
            }
        }
        if (!part.renameTo(dest)) error("non riesco a salvare il modello vocale")
    }

    @Synchronized
    fun ensure(ctx: Context) {
        if (loaded) return
        System.loadLibrary("nexuswhisper")
        if (!load(modelFile(ctx).path)) error("modello vocale non caricato")
        loaded = true
    }

    @Synchronized
    fun release() { if (loaded) { runCatching { free() }; loaded = false } }
}
