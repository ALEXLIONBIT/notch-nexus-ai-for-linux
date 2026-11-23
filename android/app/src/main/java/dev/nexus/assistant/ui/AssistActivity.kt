package dev.nexus.assistant.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import dev.nexus.assistant.assist.NexusSession
import dev.nexus.assistant.core.Core
import dev.nexus.assistant.core.Prefs
import kotlinx.coroutines.delay

/** Finestra dell'assistente: si apre dal tasto laterale e sta sopra l'app che stai usando. */
class AssistActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AssistSheet(onClose = { close() }) }
        startListeningIfPossible()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        startListeningIfPossible()
    }

    private fun startListeningIfPossible() {
        if (Prefs.providers.isEmpty()) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            startActivity(Intent(this, MainActivity::class.java).putExtra("askMic", true)); finish(); return
        }
        if (Core.state == "idle" || Core.state == "error") Core.listen()
    }

    private fun close() {
        if (Core.state == "listening") Core.stopAll()
        finish()
    }

    override fun onDestroy() {
        NexusSession.current?.get()?.let { runCatching { it.hide() } }
        super.onDestroy()
    }

    @androidx.compose.runtime.Composable
    private fun AssistSheet(onClose: () -> Unit) {
        val th = Look.theme
        // quando NEXUS deve agire su un'altra app, la finestra si fa da parte
        val firstHide = remember { Core.hideRequest }
        LaunchedEffect(Core.hideRequest) { if (Core.hideRequest != firstHide) finish() }
        // si chiude da sola qualche secondo dopo aver finito di parlare
        LaunchedEffect(Core.state, Core.sayText) {
            if (Core.state == "idle" && Core.sayText.isEmpty() && Core.reply.isNotEmpty()) { delay(5000); finish() }
        }
        Box(Modifier.fillMaxSize().clickable(remember { MutableInteractionSource() }, null) { onClose() }) {
            BoxWithConstraints(Modifier.align(Alignment.BottomCenter).fillMaxWidth()) {
                val tablet = maxWidth > 600.dp
                Column(
                    Modifier.align(Alignment.BottomCenter).widthIn(max = 620.dp).fillMaxWidth()
                        .padding(horizontal = if (tablet) 0.dp else 8.dp, vertical = if (tablet) 24.dp else 8.dp)
                        .clip(RoundedCornerShape(30.dp)).background(Look.bg)
                        .clickable(remember { MutableInteractionSource() }, null) {}
                        .navigationBarsPadding().imePadding().padding(18.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    if (Prefs.providers.isEmpty()) {
                        Text("Prima configura NEXUS", color = th.ink, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        Text("Apri l'app e aggiungi un cervello (il tuo PC o una chiave API).", color = th.inkSoft, textAlign = TextAlign.Center)
                        Text("Apri NEXUS", color = Look.led, fontWeight = FontWeight.Bold, modifier = Modifier.clickable {
                            startActivity(Intent(this@AssistActivity, MainActivity::class.java)); finish() }.padding(8.dp))
                        return@Column
                    }
                    Helmet(Modifier.fillMaxWidth(if (tablet) .5f else .62f))
                    StatusLine()
                    if (Core.transcript.isNotBlank()) Text("Tu: " + Core.transcript, color = th.inkSoft, fontSize = 14.sp, textAlign = TextAlign.Center)
                    if (Core.sayText.isNotEmpty())
                        Subtitle(th.ink, th.inkSoft.copy(alpha = .4f), TextStyle(fontFamily = FontFamily.Monospace, fontSize = 20.sp,
                            fontWeight = FontWeight.Bold, textAlign = TextAlign.Center))
                    else if (Core.reply.isNotBlank())
                        Text(Core.reply, color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center)
                    Core.steps.takeLast(3).forEach { Text("• $it", color = th.inkSoft, fontSize = 13.sp) }
                    AskBar()
                }
            }
        }
    }
}
