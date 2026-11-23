package dev.nexus.assistant.assist

import android.content.Intent
import android.speech.RecognitionService
import android.speech.SpeechRecognizer

/** Richiesto da Android per gli assistenti: NEXUS usa il riconoscimento vocale di Google, questo resta vuoto. */
class NexusRecognitionService : RecognitionService() {
    override fun onStartListening(intent: Intent?, cb: Callback?) { cb?.error(SpeechRecognizer.ERROR_CLIENT) }
    override fun onCancel(cb: Callback?) {}
    override fun onStopListening(cb: Callback?) {}
}
