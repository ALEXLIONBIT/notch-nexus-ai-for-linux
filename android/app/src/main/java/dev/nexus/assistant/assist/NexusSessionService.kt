package dev.nexus.assistant.assist

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import dev.nexus.assistant.ui.AssistActivity
import java.lang.ref.WeakReference

class NexusSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession = NexusSession(this)
}

/** Quando tieni premuto il tasto laterale (o fai il gesto dell'assistente) si apre la finestra di NEXUS. */
class NexusSession(ctx: android.content.Context) : VoiceInteractionSession(ctx) {
    companion object { var current: WeakReference<NexusSession>? = null }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        current = WeakReference(this)
        val i = Intent(context, AssistActivity::class.java).putExtra("fromAssist", true)
        runCatching { startAssistantActivity(i) }.onFailure {
            context.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }
}
