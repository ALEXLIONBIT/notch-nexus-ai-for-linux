package dev.nexus.assistant.wear

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import dev.nexus.llama.HfFile
import dev.nexus.llama.LocalLlm
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Modelli AI che girano su questo dispositivo: stato per la UI, download e scelta come cervello. */
object DeviceBrain {
    const val ID = "device"
    var status by mutableStateOf("")
    var pct by mutableStateOf(-1)
    var busy by mutableStateOf(false)
    var results by mutableStateOf(listOf<HfFile>())
    var installed by mutableStateOf(listOf<String>())
    @Volatile private var stop = false

    fun refresh(ctx: Context) { installed = LocalLlm.installed(ctx).map { it.name } }

    fun pretty(file: String) = file.removeSuffix(".gguf").replace('_', ' ')

    /** Diventa il cervello attivo (provider "Sull'orologio"). */
    fun use(file: String) {
        val p = Provider(id = ID, name = "Sull'orologio", preset = "device", kind = "device", baseUrl = "", model = file)
        Prefs.providers = Prefs.providers.filter { it.id != ID } + p
        Prefs.activeProvider = ID
        Prefs.ownActive = true
        Prefs.save()
        Core.warmup()
    }

    fun inUse(file: String) = Prefs.activeProvider == ID && Prefs.providers.any { it.id == ID && it.model == file }

    suspend fun search(q: String) = withContext(Dispatchers.IO) {
        busy = true; status = "Cerco…"
        try {
            results = LocalLlm.search(q)
            status = if (results.isEmpty()) "Niente trovato" else ""
        } catch (e: Exception) { status = "Errore: ${e.message}" } finally { busy = false }
    }

    suspend fun download(ctx: Context, repo: String, file: String, thenUse: Boolean = true) = withContext(Dispatchers.IO) {
        if (busy) return@withContext
        busy = true; stop = false; pct = 0
        val name = file.substringAfterLast('/')
        try {
            LocalLlm.download(ctx, repo, file, { mb, tot ->
                pct = if (tot > 0) mb * 100 / tot else -1
                status = "Scarico ${pretty(name)}… $mb / $tot MB"
            }, { stop })
            refresh(ctx)
            status = "Provo il modello…"
            LocalLlm.load(ctx, name)          // controlla subito che parta su questo dispositivo
            if (thenUse) use(name)
            status = "Pronto: ${pretty(name)}"
        } catch (e: Throwable) {
            status = "Errore: ${e.message}"
        } finally { busy = false; pct = -1 }
    }

    fun cancel() { stop = true; LocalLlm.cancel() }

    fun delete(ctx: Context, file: String) {
        LocalLlm.delete(ctx, file)
        if (inUse(file)) { Prefs.providers = Prefs.providers.filter { it.id != ID }; Prefs.activeProvider = Prefs.providers.firstOrNull()?.id ?: ""; Prefs.save() }
        refresh(ctx)
    }
}
