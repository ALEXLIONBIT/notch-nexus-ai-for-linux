package dev.nexus.assistant.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.nexus.assistant.core.Llm
import dev.nexus.assistant.core.PRESETS
import dev.nexus.assistant.core.Prefs
import dev.nexus.assistant.core.Provider
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

@Composable
fun SectionTitle(t: String) = Text(t, color = Look.theme.ink, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold,
    modifier = Modifier.padding(top = 18.dp, bottom = 6.dp))

@Composable
fun Label(t: String) = Text(t, color = Look.theme.inkSoft, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
    modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))

@Composable
fun NexusField(value: String, label: String, password: Boolean = false, onChange: (String) -> Unit) {
    val th = Look.theme
    OutlinedTextField(value, onChange, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        visualTransformation = if (password) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
        keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else KeyboardType.Text),
        colors = OutlinedTextFieldDefaults.colors(focusedTextColor = th.ink, unfocusedTextColor = th.ink,
            focusedBorderColor = Look.led, unfocusedBorderColor = th.inkSoft.copy(alpha = .4f),
            focusedLabelColor = Look.led, unfocusedLabelColor = th.inkSoft, cursorColor = Look.led))
}

@Composable
fun PrimaryButton(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) =
    Text(text, color = Color(0xFF0B1015), fontWeight = FontWeight.Bold, fontSize = 16.sp,
        modifier = modifier.clip(RoundedCornerShape(50)).background(Look.led).clickable { onClick() }
            .padding(horizontal = 18.dp, vertical = 12.dp))

@Composable
fun SoftButton(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) =
    Text(text, color = Look.theme.ink, fontWeight = FontWeight.SemiBold, fontSize = 14.sp,
        modifier = modifier.clip(RoundedCornerShape(50)).background(chipColor()).clickable { onClick() }
            .padding(horizontal = 16.dp, vertical = 10.dp))

private val SWATCHES = listOf(0xFF9BE7FF, 0xFFF4F7FA, 0xFF8CF5C8, 0xFFFF9FD8, 0xFFFFC861, 0xFFB9A6FF, 0xFFFF5A6E, 0xFF3DAEE9,
    0xFF7DFF6B, 0xFFFF8A3D, 0xFFFFE14D, 0xFF4DFFE1, 0xFFE14DFF, 0xFF2E7DFF, 0xFFFFFFFF, 0xFF8A96A3, 0xFF2A2E35, 0xFF000000,
    0xFFF6F7F8, 0xFFF07A1A, 0xFF0F2A1F, 0xFF170C24, 0xFF1B1E20, 0xFFD62839).map { it.toInt() }

/** Scelta colore: tavolozza + codice esadecimale (qualsiasi colore). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ColorDialog(title: String, initial: Int, allowReset: Boolean, onPick: (Int) -> Unit, onReset: () -> Unit, onDismiss: () -> Unit) {
    var hex by remember { mutableStateOf("#%06X".format(initial and 0xFFFFFF)) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = {
        Column {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SWATCHES.forEach { c ->
                    Box(Modifier.size(36.dp).clip(CircleShape).background(Color(c)).border(1.dp, Color.Gray, CircleShape)
                        .clickable { onPick(c); onDismiss() })
                }
            }
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(hex, { hex = it }, label = { Text("Codice colore (#RRGGBB)") }, singleLine = true)
        }
    }, confirmButton = {
        TextButton({ runCatching { onPick(android.graphics.Color.parseColor(hex.trim().let { if (it.startsWith("#")) it else "#$it" })) }; onDismiss() }) { Text("Usa") }
    }, dismissButton = { if (allowReset) TextButton({ onReset(); onDismiss() }) { Text("Colore del tema") } })
}

// ====================================================================== ASPETTO
@Composable
fun LookScreen(tablet: Boolean) {
    var editor by remember { mutableStateOf(false) }
    if (editor) { EditorScreen(tablet) { editor = false }; return }
    val preview: @Composable (Modifier) -> Unit = { m ->
        Box(m.clip(RoundedCornerShape(26.dp)).background(Look.theme.bg).border(1.dp, Look.theme.inkSoft.copy(alpha = .2f), RoundedCornerShape(26.dp))
            .padding(18.dp), contentAlignment = Alignment.Center) { Helmet(Modifier.fillMaxWidth(.8f)) }
    }
    if (tablet) {
        Row(Modifier.fillMaxSize().padding(24.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            preview(Modifier.weight(1f).fillMaxHeight())
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) { LookOptions { editor = true } }
        }
    } else {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp)) {
            Text("Aspetto", color = Look.theme.ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(10.dp))
            preview(Modifier.fillMaxWidth().height(230.dp))
            LookOptions { editor = true }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun LookOptions(openEditor: () -> Unit) {
    val th = Look.theme
    var picking by remember { mutableStateOf("") }
    SectionTitle("Tema")
    FlowRow(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        THEMES.forEach { t ->
            Column(Modifier.width(104.dp).clip(RoundedCornerShape(16.dp)).background(t.bg)
                .border(if (Prefs.theme == t.key) 3.dp else 1.dp, if (Prefs.theme == t.key) th.ink else th.inkSoft.copy(alpha = .3f), RoundedCornerShape(16.dp))
                .clickable { Look.applyTheme(t.key) }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.fillMaxWidth(.8f).aspectRatio(2.1f).clip(RoundedCornerShape(50)).background(t.shellMid).padding(4.dp)) {
                    Row(Modifier.fillMaxSize().clip(RoundedCornerShape(50)).background(t.glass), horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically) {
                        repeat(2) { Box(Modifier.size(7.dp).clip(if (t.key == "halloween") RoundedCornerShape(1.dp) else CircleShape).background(t.led)) }
                    }
                }
                Spacer(Modifier.height(6.dp))
                Text(t.name, color = t.ink, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
    SectionTitle("Colori")
    ColorRow("Principale (occhi)", Look.led, true) { picking = "led" }
    ColorRow("Secondario (bocca, antenne)", Look.accent, Prefs.accent != 0) { picking = "accent" }
    ColorRow("Guscio", Look.shellMid, Prefs.shellCustom != 0) { picking = "shell" }
    ColorRow("Sfondo", Look.bg, Prefs.bgCustom != 0) { picking = "bg" }
    if (picking.isNotEmpty()) ColorDialog(
        title = mapOf("led" to "Colore principale", "accent" to "Colore secondario", "shell" to "Guscio", "bg" to "Sfondo")[picking]!!,
        initial = when (picking) { "led" -> Prefs.led; "accent" -> Look.accent.toArgbInt(); "shell" -> Look.shellMid.toArgbInt(); else -> Look.bg.toArgbInt() },
        allowReset = picking != "led",
        onPick = { c -> when (picking) { "led" -> Prefs.led = c; "accent" -> Prefs.accent = c; "shell" -> Prefs.shellCustom = c; else -> Prefs.bgCustom = c }; Prefs.save() },
        onReset = { when (picking) { "accent" -> Prefs.accent = 0; "shell" -> Prefs.shellCustom = 0; else -> Prefs.bgCustom = 0 }; Prefs.save() },
        onDismiss = { picking = "" })

    SectionTitle("Faccia")
    PrimaryButton("Disegna il tuo robot", Modifier.fillMaxWidth()) { openEditor() }
    Label("Occhi")
    Chips(listOf("tondi", "quadrati", "linee", "triangoli", "cuori", "disegnati"),
        listOf("Tondi", "Quadrati", "Linee", "Triangoli", "Cuori", "Disegnati da te"), Prefs.eyeStyle) { Prefs.eyeStyle = it; Prefs.save() }
    Label("Bocca")
    Chips(listOf("sorriso", "linea", "o", "zigzag", "disegnata"),
        listOf("Sorriso", "Linea", "Tonda", "Zig zag", "Disegnata da te"), Prefs.mouthStyle) { Prefs.mouthStyle = it; Prefs.save() }
    Label("LED")
    Chips(listOf("tondi", "quadrati"), listOf("Tondi", "Quadrati (pixel)"), Prefs.dotShape) { Prefs.dotShape = it; Prefs.save() }
    Label("Bagliore ${(Prefs.glow * 100).toInt()}%")
    Slider(Prefs.glow, { Prefs.glow = it }, onValueChangeFinished = { Prefs.save() },
        colors = SliderDefaults.colors(thumbColor = th.ink, activeTrackColor = th.ink))

    SectionTitle("Corpo")
    Label("Forma del casco")
    Chips(listOf("capsula", "tondo", "tv", "cubo"), listOf("Capsula", "Tondo", "TV", "Cubo"), Prefs.helmetShape) { Prefs.helmetShape = it; Prefs.save() }
    Label("Antenna")
    Chips(listOf("nessuna", "una", "due"), listOf("Nessuna", "Una", "Due"), Prefs.antenna) { Prefs.antenna = it; Prefs.save() }
    Label("Orecchie")
    Chips(listOf("si", "no"), listOf("Sì", "No"), if (Prefs.ears) "si" else "no") { Prefs.ears = it == "si"; Prefs.save() }

    SectionTitle("Voce")
    Label("Velocità %.2f×".format(Prefs.speechRate))
    Slider(Prefs.speechRate, { Prefs.speechRate = it }, valueRange = .6f..1.8f, onValueChangeFinished = { Prefs.save() },
        colors = SliderDefaults.colors(thumbColor = th.ink, activeTrackColor = th.ink))
    Label("Tono (più basso = più robot) %.2f".format(Prefs.speechPitch))
    Slider(Prefs.speechPitch, { Prefs.speechPitch = it }, valueRange = .5f..1.5f, onValueChangeFinished = { Prefs.save() },
        colors = SliderDefaults.colors(thumbColor = th.ink, activeTrackColor = th.ink))
    Label("Riascolta da solo se ti fa una domanda")
    Chips(listOf("si", "no"), listOf("Sì", "No"), if (Prefs.autoListen) "si" else "no") { Prefs.autoListen = it == "si"; Prefs.save() }
    Spacer(Modifier.height(30.dp))
}

@Composable
private fun ColorRow(label: String, color: Color, custom: Boolean, onClick: () -> Unit) {
    val th = Look.theme
    Row(Modifier.fillMaxWidth().clickable { onClick() }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(40.dp).clip(CircleShape).background(color).border(1.dp, th.inkSoft, CircleShape))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(label, color = th.ink, fontWeight = FontWeight.Bold)
            Text(if (custom) "#%06X".format(color.toArgbInt() and 0xFFFFFF) else "Quello del tema", color = th.inkSoft, fontSize = 12.sp)
        }
        SoftButton("Cambia") { onClick() }
    }
}

// ====================================================================== EDITOR
@Composable
fun EditorScreen(tablet: Boolean, onDone: () -> Unit) {
    val th = Look.theme
    var brush by remember { mutableIntStateOf(1) }
    var editColor by remember { mutableIntStateOf(-1) }
    remember { Prefs.eyeStyle = "disegnati"; Prefs.mouthStyle = "disegnata"; Prefs.save(); 0 }

    fun setCell(eye: Boolean, idx: Int, v: Int) {
        val s = if (eye) Prefs.customEye else Prefs.customMouth
        if (idx !in s.indices || s[idx].digitToIntOrNull() == v) return
        val n = s.substring(0, idx) + v + s.substring(idx + 1)
        if (eye) Prefs.customEye = n else Prefs.customMouth = n
    }

    @Composable
    fun Grid(eye: Boolean, cols: Int, rows: Int, modifier: Modifier) {
        val data = if (eye) Prefs.customEye else Prefs.customMouth
        var paintValue by remember { mutableIntStateOf(1) }
        Box(modifier.aspectRatio(cols.toFloat() / rows).clip(RoundedCornerShape(16.dp)).background(th.glass).padding(6.dp)) {
            Box(Modifier.fillMaxSize().pointerInput(eye, brush) {
                fun idx(o: Offset): Int {
                    val cx = (o.x / (size.width / cols)).toInt(); val cy = (o.y / (size.height / rows)).toInt()
                    return if (cx in 0 until cols && cy in 0 until rows) cy * cols + cx else -1
                }
                detectDragGestures(onDragStart = { o ->
                    val i = idx(o); if (i >= 0) {
                        val cur = (if (eye) Prefs.customEye else Prefs.customMouth)[i].digitToIntOrNull() ?: 0
                        paintValue = if (cur == brush && brush != 0) 0 else brush; setCell(eye, i, paintValue) }
                }, onDragEnd = { Prefs.save() }) { change, _ -> val i = idx(change.position); if (i >= 0) setCell(eye, i, paintValue) }
            }.pointerInput(eye, brush) {
                detectTapGestures { o ->
                    val cx = (o.x / (size.width / cols)).toInt(); val cy = (o.y / (size.height / rows)).toInt()
                    if (cx in 0 until cols && cy in 0 until rows) {
                        val i = cy * cols + cx
                        val cur = (if (eye) Prefs.customEye else Prefs.customMouth)[i].digitToIntOrNull() ?: 0
                        setCell(eye, i, if (cur == brush && brush != 0) 0 else brush); Prefs.save()
                    }
                }
            }) {
                Column(Modifier.fillMaxSize()) {
                    for (r in 0 until rows) Row(Modifier.weight(1f).fillMaxWidth()) {
                        for (c in 0 until cols) {
                            val v = data.getOrNull(r * cols + c)?.digitToIntOrNull() ?: 0
                            Box(Modifier.weight(1f).fillMaxHeight().padding(2.dp)
                                .clip(if (Prefs.dotShape == "quadrati") RoundedCornerShape(3.dp) else CircleShape)
                                .background(if (v == 0) th.ledOff else Color(Prefs.paletteColor(v))))
                        }
                    }
                }
            }
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Disegna il tuo robot", color = th.ink, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, modifier = Modifier.weight(1f))
            PrimaryButton("Fatto") { Prefs.save(); onDone() }
        }
        Text("Scegli un colore e trascina sui LED. Tocca di nuovo un colore per cambiarlo.", color = th.inkSoft, fontSize = 13.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            for (i in 0..8) {
                Box(Modifier.size(38.dp).clip(CircleShape).background(if (i == 0) Color.Transparent else Color(Prefs.paletteColor(i)))
                    .border(if (brush == i) 3.dp else 1.dp, if (brush == i) th.ink else th.inkSoft, CircleShape)
                    .clickable { if (brush == i && i > 0) editColor = i; brush = i }, contentAlignment = Alignment.Center) {
                    if (i == 0) Text("✕", color = th.inkSoft)
                }
            }
        }
        if (editColor > 0) ColorDialog(if (editColor == 1) "Colore principale" else "Colore $editColor", Prefs.paletteColor(editColor), false,
            onPick = { c -> if (editColor == 1) Prefs.led = c else Prefs.palette = Prefs.palette.toMutableList().also { it[editColor - 2] = c }; Prefs.save() },
            onReset = {}, onDismiss = { editColor = -1 })

        val eyeBlock: @Composable (Modifier) -> Unit = { m ->
            Column(m, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Occhio", color = th.ink, fontWeight = FontWeight.Bold)
                Grid(true, Prefs.EYE_COLS, Prefs.EYE_ROWS, Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SoftButton("Specchia") {
                        val a = Prefs.customEye.toCharArray(); val c = Prefs.EYE_COLS
                        for (r in 0 until Prefs.EYE_ROWS) for (x in 0 until c / 2) a[r * c + (c - 1 - x)] = a[r * c + x]
                        Prefs.customEye = String(a); Prefs.save()
                    }
                    SoftButton("Riempi") { Prefs.customEye = "$brush".repeat(Prefs.EYE_COLS * Prefs.EYE_ROWS); Prefs.save() }
                    SoftButton("Pulisci") { Prefs.customEye = "0".repeat(Prefs.EYE_COLS * Prefs.EYE_ROWS); Prefs.save() }
                }
            }
        }
        val mouthBlock: @Composable (Modifier) -> Unit = { m ->
            Column(m, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Bocca", color = th.ink, fontWeight = FontWeight.Bold)
                Grid(false, Prefs.MOUTH_COLS, Prefs.MOUTH_ROWS, Modifier.fillMaxWidth())
                SoftButton("Pulisci") { Prefs.customMouth = "0".repeat(Prefs.MOUTH_COLS * Prefs.MOUTH_ROWS); Prefs.save() }
                Text("Anteprima", color = th.ink, fontWeight = FontWeight.Bold)
                Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(th.glass).padding(14.dp)) {
                    DotFace(Modifier.fillMaxWidth(), forceMood = "idle")
                }
            }
        }
        if (tablet) Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) { eyeBlock(Modifier.weight(1f)); mouthBlock(Modifier.weight(1f)) }
        else { eyeBlock(Modifier.fillMaxWidth(.85f)); mouthBlock(Modifier.fillMaxWidth()) }
    }
}

// ====================================================================== CERVELLO
@Composable
fun BrainScreen() {
    val th = Look.theme
    var editing by remember { mutableStateOf<Provider?>(null) }
    var adding by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Cervello", color = th.ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
        Text("Dove gira l'intelligenza: il tuo PC (in casa o via Tailscale), un servizio online con chiave API, " +
            "oppure un modello che gira sul telefono, anche senza internet.", color = th.inkSoft, fontSize = 14.sp)
        Prefs.providers.forEach { p ->
            val on = Prefs.active()?.id == p.id
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(if (on) chipColor() else Color.Transparent)
                .border(if (on) 2.dp else 1.dp, if (on) th.ink else th.inkSoft.copy(alpha = .3f), RoundedCornerShape(18.dp))
                .clickable { Prefs.activeProvider = p.id; Prefs.save() }.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(16.dp).clip(CircleShape).border(2.dp, th.ink, CircleShape), contentAlignment = Alignment.Center) {
                    if (on) Box(Modifier.size(8.dp).clip(CircleShape).background(th.ink))
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(p.name, color = th.ink, fontWeight = FontWeight.Bold)
                    Text("${p.model.ifBlank { "—" }} · ${p.baseUrl.removePrefix("http://").removePrefix("https://")}", color = th.inkSoft, fontSize = 12.sp, maxLines = 1)
                }
                SoftButton("Modifica") { editing = p }
            }
        }
        PrimaryButton("+ Aggiungi cervello", Modifier.fillMaxWidth()) { adding = true }
        Spacer(Modifier.height(8.dp))
        NameSection()
        Spacer(Modifier.height(8.dp))
        DeviceModelsSection()
        Spacer(Modifier.height(8.dp))
        SectionTitle("Tailscale")
        Text("Per usare il PC di casa anche fuori casa senza l'app Tailscale: NEXUS si collega da solo alla tua rete Tailscale.",
            color = th.inkSoft, fontSize = 13.sp)
        val tsCtx = androidx.compose.ui.platform.LocalContext.current
        val TsO = dev.nexus.assistant.core.Ts
        Text("Stato: " + TsO.label + if (TsO.name.isNotBlank()) " (${TsO.name.substringBefore('.')})" else "", color = th.ink, fontSize = 13.sp)
        androidx.compose.runtime.LaunchedEffect(TsO.authUrl) {
            if (TsO.state == "NeedsLogin" && TsO.authUrl.isNotBlank() && Prefs.tailscale)
                runCatching { tsCtx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(TsO.authUrl))) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (TsO.state != "Running") SoftButton("Collega", Modifier.weight(1f)) {
                Prefs.tailscale = true; Prefs.save(); TsO.start(tsCtx, "nexus-telefono")
            } else SoftButton("Scollega", Modifier.weight(1f)) { TsO.logout(); Prefs.tailscale = false; Prefs.save() }
            val tsScope = androidx.compose.runtime.rememberCoroutineScope()
            SoftButton("Collega anche l'orologio", Modifier.weight(1f)) {
                tsScope.launch {
                    dev.nexus.assistant.core.WatchSync.status = runCatching {
                        val nodes = com.google.android.gms.wearable.Wearable.getNodeClient(tsCtx).connectedNodes.await()
                        if (nodes.isEmpty()) "Nessun orologio collegato" else {
                            nodes.forEach { com.google.android.gms.wearable.Wearable.getMessageClient(tsCtx).sendMessage(it.id, "/nexus/tailscale", ByteArray(0)).await() }
                            "Fra poco si apre qui il login per l'orologio: approvalo."
                        }
                    }.getOrElse { "Non riesco: ${it.message?.take(60)}" }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        SectionTitle("Orologio Wear OS")
        Text("Con NEXUS per Wear OS sull'orologio, cervelli e aspetto arrivano da soli. Se non succede, premi qui.",
            color = th.inkSoft, fontSize = 13.sp)
        val ctx = androidx.compose.ui.platform.LocalContext.current
        val scope = androidx.compose.runtime.rememberCoroutineScope()
        SoftButton("Invia all'orologio", Modifier.fillMaxWidth()) {
            dev.nexus.assistant.core.WatchSync.status = "Invio…"
            scope.launch { dev.nexus.assistant.core.WatchSync.send(ctx) }
        }
        if (dev.nexus.assistant.core.WatchSync.status.isNotBlank())
            Text(dev.nexus.assistant.core.WatchSync.status, color = th.inkSoft, fontSize = 12.sp)
    }
    if (adding || editing != null) ProviderDialog(editing) { adding = false; editing = null }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProviderDialog(existing: Provider?, onClose: () -> Unit) {
    val scope = rememberCoroutineScope()
    var preset by remember { mutableStateOf(existing?.preset ?: "ollama") }
    val pr = PRESETS.firstOrNull { it.key == preset } ?: PRESETS[0]
    var name by remember { mutableStateOf(existing?.name ?: pr.label) }
    var url by remember { mutableStateOf(existing?.baseUrl ?: pr.baseUrl) }
    var key by remember { mutableStateOf("") }
    var model by remember { mutableStateOf(existing?.model ?: pr.model) }
    var msg by remember { mutableStateOf("") }
    var models by remember { mutableStateOf(listOf<String>()) }
    fun draft() = Provider(id = existing?.id ?: java.util.UUID.randomUUID().toString().take(8), name = name.ifBlank { pr.label },
        preset = preset, kind = pr.kind, baseUrl = url.trim(), apiKey = key.trim().ifBlank { existing?.apiKey ?: "" }, model = model.trim())

    AlertDialog(onDismissRequest = onClose, title = { Text(if (existing != null) "Modifica cervello" else "Aggiungi cervello") }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                PRESETS.forEach { p ->
                    Text(p.label.substringBefore(" ("), fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                        color = if (preset == p.key) Color.White else Color.Unspecified,
                        modifier = Modifier.clip(RoundedCornerShape(50)).background(if (preset == p.key) Color(0xFF1F242B) else Color(0x22888888))
                            .clickable { preset = p.key; if (existing == null) name = p.label.substringBefore(" ("); url = p.baseUrl; model = p.model; models = emptyList(); msg = "" }
                            .padding(horizontal = 10.dp, vertical = 6.dp))
                }
            }
            if (pr.hint.isNotBlank()) Text(pr.hint, fontSize = 12.sp, color = Color.Gray)
            OutlinedTextField(name, { name = it }, label = { Text("Nome") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(url, { url = it }, label = { Text("Indirizzo (URL)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(key, { key = it }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                label = { Text(if (existing?.apiKey?.isNotBlank() == true) "Chiave API (vuoto = tieni quella salvata)"
                               else if (pr.needsKey) "Chiave API" else "Chiave API (se il server la chiede)") },
                visualTransformation = PasswordVisualTransformation())
            OutlinedTextField(model, { model = it }, label = { Text("Modello") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton({ msg = "Carico…"; scope.launch { runCatching { Llm.models(draft()) }.onSuccess { models = it; msg = "${it.size} modelli" }.onFailure { msg = "Errore: ${it.message}" } } }) { Text("Carica modelli") }
                TextButton({ msg = "Provo…"; scope.launch { runCatching { Llm.models(draft()) }.onSuccess { msg = "Connesso! ${it.size} modelli disponibili" }.onFailure { msg = "Connessione fallita: ${it.message}" } } }) { Text("Prova") }
            }
            if (msg.isNotBlank()) Text(msg, fontSize = 13.sp, color = if (msg.startsWith("Errore") || msg.startsWith("Connessione fallita")) Color(0xFFFF5A6E) else Color(0xFF3FB27F))
            if (models.isNotEmpty()) LazyColumn(Modifier.fillMaxWidth().heightIn(max = 180.dp)) {
                items(models) { m -> Text(m, fontSize = 13.sp, fontWeight = if (m == model) FontWeight.Bold else FontWeight.Normal,
                    modifier = Modifier.fillMaxWidth().clickable { model = m }.padding(vertical = 6.dp)) }
            }
            if (existing != null && Prefs.providers.size > 1) TextButton({ Prefs.remove(existing.id); onClose() }) { Text("Elimina", color = Color(0xFFFF5A6E)) }
        }
    }, confirmButton = { TextButton({ Prefs.upsert(draft(), true); onClose() }) { Text("Salva e usa") } },
        dismissButton = { TextButton(onClose) { Text("Annulla") } })
}


/** Modelli AI che girano sul telefono (llama.cpp): consigliati, ricerca su Hugging Face, scarica, usa, elimina. */
@Composable
private fun DeviceModelsSection() {
    val th = Look.theme
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    val DB = dev.nexus.assistant.core.DeviceBrain
    val LL = dev.nexus.llama.LocalLlm
    androidx.compose.runtime.LaunchedEffect(Unit) { DB.refresh(ctx) }
    val ram = remember { LL.ramMb(ctx) }
    SectionTitle("Modelli sul telefono")
    Text("Girano sul telefono, anche senza internet. Più sono grandi, più sono intelligenti ma lenti. " +
        "Questo telefono ha ${"%.1f".format(ram / 1024f)} GB di RAM.", color = th.inkSoft, fontSize = 13.sp)
    if (DB.installed.isNotEmpty()) Label("Sul telefono")
    DB.installed.forEach { f ->
        val on = DB.inUse(f)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text((if (on) "● " else "") + DB.pretty(f), color = th.ink, fontWeight = if (on) FontWeight.Bold else FontWeight.Normal, maxLines = 1)
                Text("${LL.fileFor(ctx, f).length() / (1024 * 1024)} MB", color = th.inkSoft, fontSize = 12.sp)
            }
            if (!on) SoftButton("Usa") { DB.use(f) }
            Spacer(Modifier.width(6.dp))
            SoftButton("Elimina") { DB.delete(ctx, f) }
        }
    }
    Label("Consigliati")
    LL.CATALOG.filter { it.file !in DB.installed }.forEach { m ->
        val ok = LL.fits(ctx, m.sizeMb)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(m.name + " · " + m.sizeMb + " MB", color = if (ok) th.ink else th.inkSoft, fontWeight = FontWeight.SemiBold)
                Text(if (ok) m.note else "Troppo grande per questo telefono", color = th.inkSoft, fontSize = 12.sp)
            }
            if (ok) SoftButton(if (DB.busy) "…" else "Scarica") {
                if (!DB.busy) scope.launch { DB.download(ctx, m.repo, m.file) }
            }
        }
    }
    var q by remember { mutableStateOf("") }
    Label("Cerca su Hugging Face")
    NexusField(q, "es. qwen, gemma, llama, phi, mistral") { q = it }
    SoftButton("Cerca", Modifier.fillMaxWidth()) { if (q.isNotBlank() && !DB.busy) scope.launch { DB.search(q) } }
    DB.results.forEach { r ->
        val ok = LL.fits(ctx, r.sizeMb)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(r.repo.substringAfter('/'), color = th.ink, fontWeight = FontWeight.SemiBold, maxLines = 1)
                Text("${r.file.substringAfterLast('/')} · ${r.sizeMb} MB" + if (!ok) " · troppo grande" else "",
                    color = th.inkSoft, fontSize = 12.sp, maxLines = 1)
            }
            if (ok && r.file.substringAfterLast('/') !in DB.installed) SoftButton("Scarica") {
                if (!DB.busy) scope.launch { DB.download(ctx, r.repo, r.file) }
            }
        }
    }
    if (DB.status.isNotBlank()) Text(DB.status, color = if (DB.status.startsWith("Errore")) Color(0xFFFF5A6E) else th.ink, fontSize = 13.sp)
    if (DB.pct >= 0) androidx.compose.material3.LinearProgressIndicator(progress = { DB.pct / 100f }, modifier = Modifier.fillMaxWidth(), color = Look.led)
    if (DB.busy && DB.pct >= 0) SoftButton("Annulla", Modifier.fillMaxWidth()) { DB.cancel() }
}

/** Chat salvate: cerca, apri (si continua a parlare da dove eri rimasto), nuova, elimina. */
@Composable
fun ChatsScreen(onOpen: () -> Unit) {
    val th = Look.theme
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val C = dev.nexus.assistant.core.Chats
    var q by remember { mutableStateOf("") }
    var refresh by remember { mutableIntStateOf(0) }
    val list = remember(q, refresh, dev.nexus.assistant.core.Core.chat.size) { C.list(ctx, q) }
    Column(Modifier.fillMaxSize().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Chat", color = th.ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, modifier = Modifier.weight(1f))
            PrimaryButton("+ Nuova") { dev.nexus.assistant.core.Core.newChat(); onOpen() }
        }
        NexusField(q, "Cerca nelle chat") { q = it }
        if (list.isEmpty()) Text(if (q.isBlank()) "Ancora nessuna chat: parla o scrivi a NEXUS." else "Nessuna chat con “$q”",
            color = th.inkSoft, fontSize = 14.sp, modifier = Modifier.padding(top = 20.dp))
        androidx.compose.foundation.lazy.LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(list.size) { i ->
                val c = list[i]
                val on = c.id == dev.nexus.assistant.core.Core.chatId
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(if (on) chipColor() else Color.Transparent)
                    .clickable { dev.nexus.assistant.core.Core.openChat(c.id); onOpen() }.padding(horizontal = 14.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(c.title, color = th.ink, fontWeight = FontWeight.Bold, maxLines = 1, modifier = Modifier.weight(1f))
                            Text(C.whenText(c.updated), color = th.inkSoft, fontSize = 11.sp)
                        }
                        Text(c.preview, color = th.inkSoft, fontSize = 13.sp, maxLines = 2)
                    }
                    Spacer(Modifier.width(8.dp))
                    Text("✕", color = th.inkSoft, fontSize = 16.sp, modifier = Modifier.clip(CircleShape).clickable {
                        C.delete(ctx, c.id)
                        if (on) dev.nexus.assistant.core.Core.newChat()
                        refresh++
                    }.padding(8.dp))
                }
            }
        }
    }
}


/** Come si chiama l'agente e ascolto sempre attivo del suo nome ("Ehi Marco"). */
@Composable
private fun NameSection() {
    val th = Look.theme
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    val W = dev.nexus.assistant.core.WakeService
    var name by remember { mutableStateOf(Prefs.agentName) }
    var msg by remember { mutableStateOf("") }
    val perms = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()) { W.start(ctx) }
    SectionTitle("Nome")
    Text("Dagli il nome che vuoi: si presenta così e, con l'ascolto sempre attivo, si sveglia quando lo chiami.",
        color = th.inkSoft, fontSize = 13.sp)
    NexusField(name, "Come si chiama (es. Marco, Jarvis, Robo)") { name = it.take(30) }
    if (name.trim().isNotBlank() && name.trim() != Prefs.agentName)
        SoftButton("Salva il nome", Modifier.fillMaxWidth()) {
            Prefs.agentName = name.trim(); Prefs.save()
            if (W.running) { W.stop(ctx); W.start(ctx) }
        }
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("Ascolto sempre attivo", color = th.ink, fontWeight = FontWeight.SemiBold)
            Text(if (W.running) "Di' “Ehi ${Prefs.agentName}” anche a schermo spento" else "Spento: si attiva col tasto o aprendo l'app",
                color = th.inkSoft, fontSize = 12.sp)
        }
        androidx.compose.material3.Switch(checked = Prefs.wakeAlways, onCheckedChange = { on ->
            Prefs.wakeAlways = on; Prefs.save()
            if (!on) { W.stop(ctx); msg = ""; return@Switch }
            scope.launch {
                if (!dev.nexus.whisper.WhisperNative.ready(ctx)) {
                    msg = "Scarico il riconoscimento vocale…"
                    val r = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                        runCatching { dev.nexus.whisper.WhisperNative.download(ctx) { mb, tot -> msg = "Scarico il riconoscimento vocale… $mb / $tot MB" } }
                    }
                    if (r.isFailure) { msg = "Errore: ${r.exceptionOrNull()?.message}"; Prefs.wakeAlways = false; Prefs.save(); return@launch }
                }
                msg = "Consuma un po' di batteria: Android mostra una notifica fissa finché è acceso."
                val need = mutableListOf(android.Manifest.permission.RECORD_AUDIO)
                if (android.os.Build.VERSION.SDK_INT >= 33) need += android.Manifest.permission.POST_NOTIFICATIONS
                perms.launch(need.toTypedArray())
            }
        }, colors = androidx.compose.material3.SwitchDefaults.colors(checkedTrackColor = Look.led))
    }
    if (msg.isNotBlank()) Text(msg, color = if (msg.startsWith("Errore")) Color(0xFFFF5A6E) else th.inkSoft, fontSize = 12.sp)
    if (W.lastHeard.isNotBlank()) Text("Ultima volta ho sentito: “${W.lastHeard}”", color = th.inkSoft, fontSize = 12.sp)
}
