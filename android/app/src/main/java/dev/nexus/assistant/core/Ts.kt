package dev.nexus.assistant.core

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Proxy
import java.net.ProxySelector
import java.net.SocketAddress
import java.net.URI

/** Tailscale dentro NEXUS (tsnet, libreria tsbridge): l'app è un nodo della tua rete Tailscale, senza VPN di sistema. */
object Ts {
    var state by mutableStateOf("Spento")      // Spento | Starting | NeedsLogin | Running | NeedsMachineAuth | Errore
    var authUrl by mutableStateOf("")
    var ip by mutableStateOf("")
    var name by mutableStateOf("")
    var error by mutableStateOf("")
    var log by mutableStateOf("")               // ultima riga del log di tsnet (dove si trova)
    @Volatile var port = 0
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var poll: Job? = null

    val available: Boolean get() = runCatching { Class.forName("dev.nexus.ts.tsbridge.Tsbridge"); true }.getOrDefault(false)

    /** Indirizzi della rete Tailscale: 100.64.0.0/10 e i nomi *.ts.net. */
    fun isTailnet(host: String): Boolean {
        if (host.endsWith(".ts.net")) return true
        val p = host.split(".").mapNotNull { it.toIntOrNull() }
        return p.size == 4 && p[0] == 100 && p[1] in 64..127
    }

    /** Per OkHttp: solo gli indirizzi Tailscale passano dal nodo dentro l'app. */
    val selector = object : ProxySelector() {
        override fun select(uri: URI?): List<Proxy> {
            val h = uri?.host ?: return listOf(Proxy.NO_PROXY)
            return if (port > 0 && isTailnet(h)) listOf(Proxy(Proxy.Type.HTTP, InetSocketAddress("127.0.0.1", port))) else listOf(Proxy.NO_PROXY)
        }
        override fun connectFailed(uri: URI?, sa: SocketAddress?, ioe: IOException?) {}
    }

    private fun interfaces(): String = buildString {
        runCatching {
            for (ni in NetworkInterface.getNetworkInterfaces()) {
                val addrs = ni.interfaceAddresses.joinToString(",") { "${it.address.hostAddress?.substringBefore('%')}/${it.networkPrefixLength}" }
                append("${ni.name} ${ni.index} ${ni.mtu} ${if (ni.isUp) 1 else 0} ${if (ni.isLoopback) 1 else 0} $addrs\n")
            }
        }
    }

    fun start(ctx: Context, hostname: String, authKey: String = "") {
        if (!available) { state = "Errore"; error = "libreria Tailscale non inclusa in questa build"; return }
        if (poll?.isActive == true) return
        state = "Starting"; error = ""
        poll = scope.launch {
            try {
                dev.nexus.ts.tsbridge.Tsbridge.setInterfaces(interfaces())
                dev.nexus.ts.tsbridge.Tsbridge.start(File(ctx.filesDir, "tailscale").apply { mkdirs() }.path, hostname, authKey)
            } catch (e: Exception) { state = "Errore"; error = e.message ?: e.toString(); return@launch }
            var n = 0
            while (isActive) {
                if (n++ % 15 == 0) runCatching { dev.nexus.ts.tsbridge.Tsbridge.setInterfaces(interfaces()) }
                val s = runCatching { JSONObject(dev.nexus.ts.tsbridge.Tsbridge.status()) }.getOrNull()
                if (s != null) {
                    val ns = s.optString("state", state)
                    if (ns != state || s.optString("log") != log) android.util.Log.i("NexusTs", s.toString())
                    state = ns; authUrl = s.optString("authURL"); log = s.optString("log")
                    ip = s.optJSONArray("ips")?.optString(0).orEmpty(); name = s.optString("name"); error = s.optString("error")
                    if (state == "Running" && port == 0) port = runCatching { dev.nexus.ts.tsbridge.Tsbridge.proxyPort().toInt() }.getOrDefault(0)
                }
                delay(if (state == "Running") 10_000 else 1_500)
            }
        }
    }

    fun logout() {
        scope.launch { runCatching { dev.nexus.ts.tsbridge.Tsbridge.logout() }; state = "NeedsLogin"; port = 0 }
    }

    val label: String get() = when (state) {
        "Running" -> "Collegato" + if (ip.isNotBlank()) " · $ip" else ""
        "NeedsMachineAuth" -> "In attesa di approvazione"
        "Starting", "NoState" -> "Mi collego…"
        "NeedsLogin" -> if (authUrl.isBlank()) "Mi collego…" else "Serve il login"
        "Errore" -> "Errore: ${error.take(50)}"
        else -> "Spento"
    }
}
