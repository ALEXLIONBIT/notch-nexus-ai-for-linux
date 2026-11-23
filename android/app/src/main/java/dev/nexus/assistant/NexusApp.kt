package dev.nexus.assistant

import android.app.Application
import dev.nexus.assistant.core.Core
import dev.nexus.assistant.core.Prefs

class NexusApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
        Core.init(this)
    }
}
