package dev.nexus.assistant.wear

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.tasks.await

/** Impostazioni dal telefono: l'app NEXUS del telefono pubblica un DataItem "/nexus/config" (JSON). */
object Sync {
    const val PATH = "/nexus/config"
    const val REQUEST = "/nexus/request"
    var status by mutableStateOf("")

    /** Legge l'ultima configurazione già arrivata (anche se l'app era chiusa). */
    suspend fun pull(ctx: Context): Boolean = runCatching {
        val items = Wearable.getDataClient(ctx).dataItems.await()
        var got = false
        try {
            for (item in items) if (item.uri.path == PATH) {
                DataMapItem.fromDataItem(item).dataMap.getString("json")?.let { Prefs.applyFromPhone(it); got = true }
            }
        } finally { items.release() }
        got
    }.getOrDefault(false)

    /** Chiede al telefono di mandare subito le impostazioni. */
    suspend fun request(ctx: Context) {
        status = "Cerco il telefono…"
        try {
            val nodes = Wearable.getNodeClient(ctx).connectedNodes.await()
            if (nodes.isEmpty()) { status = "Telefono non collegato"; return }
            for (n in nodes) Wearable.getMessageClient(ctx).sendMessage(n.id, REQUEST, ByteArray(0)).await()
            status = "Chiesto a ${nodes.first().displayName}. Apri NEXUS sul telefono se non arriva."
        } catch (e: Exception) {
            status = "Non riesco: ${e.message?.take(60)}"
        }
    }
}

class SyncService : WearableListenerService() {
    override fun onMessageReceived(e: com.google.android.gms.wearable.MessageEvent) {
        if (e.path == "/nexus/tailscale") TsLogin.begin(applicationContext)
    }

    override fun onDataChanged(events: DataEventBuffer) {
        for (e in events) {
            if (e.type == DataEvent.TYPE_CHANGED && e.dataItem.uri.path == Sync.PATH) {
                DataMapItem.fromDataItem(e.dataItem).dataMap.getString("json")?.let {
                    Prefs.applyFromPhone(it)
                    Sync.status = "Impostazioni ricevute dal telefono"
                }
            }
        }
    }
}
