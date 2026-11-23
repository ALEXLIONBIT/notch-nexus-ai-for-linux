package dev.nexus.assistant.core

import android.content.ContentValues
import android.content.Context
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/** Immagini: le chiede al server di NEXUS sul PC (Z-Image-Turbo) o a un'API compatibile OpenAI. */
object Images {
    private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(420, TimeUnit.SECONDS).build()

    suspend fun generate(ctx: Context, prompt: String, shape: String): String = withContext(Dispatchers.IO) {
        val size = when (shape) { "verticale" -> "768x1024"; "orizzontale" -> "1024x768"; else -> "1024x1024" }
        var base = Prefs.imageUrl.trim().trimEnd('/')
        var key = ""
        var model = "z-image-turbo"
        if (base.isBlank()) {                      // niente server NEXUS: prova con il provider OpenAI
            val p = Prefs.active()?.takeIf { it.preset == "openai" } ?: error("Imposta il server immagini in NEXUS → Configura")
            base = p.baseUrl.trimEnd('/'); key = p.apiKey; model = "gpt-image-1"
        }
        val url = if (base.endsWith("/v1")) "$base/images/generations" else "$base/v1/images/generations"
        val body = JSONObject().put("prompt", prompt).put("size", size).put("n", 1).put("model", model)
            .put("response_format", "b64_json").toString().toRequestBody("application/json".toMediaType())
        val req = Request.Builder().url(url).post(body)
        if (key.isNotBlank()) req.header("Authorization", "Bearer $key")
        val json = http.newCall(req.build()).execute().use { r ->
            val t = r.body?.string().orEmpty(); if (!r.isSuccessful) error("server immagini: HTTP ${r.code} ${t.take(150)}"); JSONObject(t)
        }
        val bytes = Base64.decode(json.getJSONArray("data").getJSONObject(0).getString("b64_json"), Base64.DEFAULT)
        val name = "nexus-${System.currentTimeMillis()}.png"
        val local = File(ctx.filesDir, "images/$name").apply { parentFile?.mkdirs(); writeBytes(bytes) }
        // copia nella Galleria: Pictures/NEXUS
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, name); put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/NEXUS")
        }
        ctx.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)?.let { uri ->
            ctx.contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
        }
        local.absolutePath
    }
}
