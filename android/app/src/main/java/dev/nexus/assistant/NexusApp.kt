package dev.nexus.assistant

import android.app.Application
import dev.nexus.assistant.core.Core
import dev.nexus.assistant.core.Prefs

class NexusApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
        dev.nexus.assistant.core.Llm.appContext = this
        Core.init(this)
        Core.warmup()
        if (Prefs.tailscale) dev.nexus.assistant.core.Ts.start(this, "nexus-telefono")
    }
}
