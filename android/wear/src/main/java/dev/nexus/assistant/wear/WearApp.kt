package dev.nexus.assistant.wear

import android.app.Application

class WearApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
        Core.init(this)
        if (Prefs.tailscale) Ts.start(this, "nexus-orologio")
    }
}
