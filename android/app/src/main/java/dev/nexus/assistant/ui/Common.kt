package dev.nexus.assistant.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.nexus.assistant.core.Core

/** Sottotitoli karaoke: le parole si accendono mentre NEXUS le dice. */
@Composable
fun Subtitle(lit: Color, dim: Color, style: TextStyle, modifier: Modifier = Modifier) {
    val s = Core.sayText
    val cut = (s.length * Core.sayProgress.coerceIn(0f, 1f)).toInt()
    val end = if (Core.sayProgress <= 0.001f) 0 else s.indexOf(' ', cut).let { if (it < 0) s.length else it }
    Text(buildAnnotatedString {
        withStyle(SpanStyle(color = lit)) { append(s.substring(0, end.coerceIn(0, s.length))) }
        withStyle(SpanStyle(color = dim)) { append(s.substring(end.coerceIn(0, s.length))) }
    }, style = style, modifier = modifier)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun Chips(options: List<String>, labels: List<String> = options, current: String, onPick: (String) -> Unit) {
    val th = Look.theme
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEachIndexed { i, o ->
            val on = o == current
            Text(labels.getOrElse(i) { o }, color = if (on) (if (th.dark) Color(0xFF16181C) else Color.White) else th.ink,
                fontSize = 14.sp, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(if (on) th.ink else chipColor())
                    .clickable { onPick(o) }.padding(horizontal = 14.dp, vertical = 9.dp))
        }
    }
}

fun chipColor() = if (Look.theme.dark) Color(0xFF2A2F36) else Color(0xFFEEF1F4)

/** Barra in basso: microfono/stop + scrivi un comando. */
@Composable
fun AskBar(modifier: Modifier = Modifier) {
    val th = Look.theme
    var text by remember { mutableStateOf("") }
    val busy = Core.state != "idle" && Core.state != "error"
    Row(modifier.fillMaxWidth().clip(RoundedCornerShape(30.dp)).background(if (th.dark) Color(0xFF22262C) else Color.White)
        .padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(if (busy) Icons.Filled.Stop else Icons.Filled.Mic, contentDescription = if (busy) "Ferma" else "Parla",
            tint = Color.White, modifier = Modifier.size(48.dp).clip(CircleShape)
                .background(if (busy) Color(0xFFD9364B) else if (th.dark) Color(0xFF3A404A) else Color(0xFF1F242B))
                .clickable { if (busy) Core.stopAll() else Core.listen() }.padding(12.dp))
        TextField(text, { text = it }, placeholder = { Text("Chiedi qualcosa…", color = th.inkSoft) },
            singleLine = true, modifier = Modifier.weight(1f).height(54.dp),
            colors = TextFieldDefaults.colors(focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent,
                focusedTextColor = th.ink, unfocusedTextColor = th.ink, cursorColor = Look.led),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
            keyboardActions = KeyboardActions(onSend = { if (text.isNotBlank()) { Core.ask(text.trim()); text = "" } }))
        if (text.isNotBlank()) Icon(Icons.AutoMirrored.Filled.Send, "Invia", tint = Color(0xFF0B1015),
            modifier = Modifier.size(44.dp).clip(CircleShape).background(Look.led).clickable { Core.ask(text.trim()); text = "" }.padding(11.dp))
    }
}

@Composable
fun StatusLine(modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        androidx.compose.foundation.layout.Box(Modifier.size(9.dp).clip(CircleShape).background(Look.stateColor))
        Text("  " + Look.statusText, color = Look.theme.inkSoft, fontSize = 15.sp, fontWeight = FontWeight.Medium)
    }
}
