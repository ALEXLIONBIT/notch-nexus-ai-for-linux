package dev.nexus.assistant.wear

import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.speech.RecognitionService
import android.speech.SpeechRecognizer

/** Registra NEXUS come "assistente digitale" dell'orologio: così può prendere il posto di Gemini. */
class NexusVoiceService : VoiceInteractionService()

class NexusSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = NexusSession(this)
}

/** Tasto dell'orologio tenuto premuto (o "Hey Google" sostituito): apre NEXUS che ascolta subito. */
class NexusSession(ctx: Context) : VoiceInteractionSession(ctx) {
    override fun onCreate() {
        super.onCreate()
        setUiEnabled(false)
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        val i = Intent(context, MainActivity::class.java).setAction(Intent.ACTION_ASSIST)
        runCatching { startAssistantActivity(i) }.onFailure {
            context.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        hide()
    }
}

/** Richiesto da Android per gli assistenti: NEXUS usa il riconoscimento dell'orologio, questo resta vuoto. */
class NexusRecognitionService : RecognitionService() {
    override fun onStartListening(intent: Intent?, cb: Callback?) { cb?.error(SpeechRecognizer.ERROR_CLIENT) }
    override fun onCancel(cb: Callback?) {}
    override fun onStopListening(cb: Callback?) {}
}

object Assist {
    private fun roles(ctx: Context) = ctx.getSystemService(RoleManager::class.java)

    /** NEXUS è l'assistente predefinito dell'orologio? */
    fun isDefault(ctx: Context): Boolean = runCatching {
        val r = roles(ctx)
        r.isRoleAvailable(RoleManager.ROLE_ASSISTANT) && r.isRoleHeld(RoleManager.ROLE_ASSISTANT)
    }.getOrDefault(false)

    /** Richiesta diretta del sistema ("Usare NEXUS come assistente?"), se l'orologio la permette. */
    fun requestIntent(ctx: Context): Intent? = runCatching {
        val r = roles(ctx)
        if (r.isRoleAvailable(RoleManager.ROLE_ASSISTANT)) r.createRequestRoleIntent(RoleManager.ROLE_ASSISTANT) else null
    }.getOrNull()?.takeIf { it.resolveActivity(ctx.packageManager) != null }

    /** Altrimenti apre la pagina delle impostazioni dove si sceglie l'assistente (la prima che esiste). */
    fun openSettings(ctx: Context): Boolean {
        val tries = listOf(
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS),
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS),
            Intent("android.settings.ASSIST_GESTURE_SETTINGS"),
            Intent(Settings.ACTION_SETTINGS),
        )
        for (i in tries) {
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (runCatching { ctx.startActivity(i) }.isSuccess) return true
        }
        return false
    }
}
