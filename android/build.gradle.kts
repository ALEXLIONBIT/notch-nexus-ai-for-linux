plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21" apply false
}

// Tailscale dentro le app (android/tsbridge, compilata da GitHub Actions): scaricata la prima volta in libs/.
val tsAar = file("libs/tsbridge.aar")
if (!tsAar.exists()) {
    tsAar.parentFile.mkdirs()
    runCatching {
        java.net.URI("https://github.com/ALEXLIONBIT/notch-nexus-ai-for-linux/releases/download/tsbridge-v1/tsbridge.aar")
            .toURL().openStream().use { input -> tsAar.outputStream().use { input.copyTo(it) } }
    }.onFailure { tsAar.delete(); logger.warn("tsbridge.aar non scaricata: le app funzionano, ma senza Tailscale dentro (${it.message})") }
}
