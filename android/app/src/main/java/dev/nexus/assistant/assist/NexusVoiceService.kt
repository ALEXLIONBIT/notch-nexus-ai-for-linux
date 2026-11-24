package dev.nexus.assistant.assist

import android.service.voice.VoiceInteractionService

/** Registra NEXUS come "assistente digitale" del telefono (al posto di Gemini/Google). */
class NexusVoiceService : VoiceInteractionService() {
    companion object {
        /** Il servizio attivo (quando NEXUS è l'assistente predefinito): da qui l'ascolto del nome apre la finestra. */
        @Volatile var instance: NexusVoiceService? = null
    }

    override fun onReady() { super.onReady(); instance = this }
    override fun onShutdown() { instance = null; super.onShutdown() }
}
