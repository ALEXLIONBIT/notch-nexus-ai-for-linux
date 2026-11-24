package dev.nexus.assistant.wear

import android.Manifest
import android.app.RemoteInput
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognizerIntent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material.Button
import androidx.wear.compose.material.ButtonDefaults
import androidx.wear.compose.material.Chip
import androidx.wear.compose.material.ChipDefaults
import androidx.wear.compose.material.Icon
import androidx.wear.compose.material.ListHeader
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.PositionIndicator
import androidx.wear.compose.material.Scaffold
import androidx.wear.compose.material.Text
import androidx.wear.compose.material.TimeText
import androidx.wear.compose.material.ToggleChip
import androidx.wear.compose.material.ToggleChipDefaults
import androidx.wear.compose.material.Vignette
import androidx.wear.compose.material.VignettePosition
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController
import androidx.wear.input.RemoteInputIntentHelper
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private var askedMic = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { App() }
        Core.scope.launch { if (Prefs.providers.isEmpty() && !Sync.pull(this@MainActivity)) Sync.request(this@MainActivity) }
        if (savedInstanceState == null) maybeListenOnOpen(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        maybeListenOnOpen(intent)
    }

    private fun maybeListenOnOpen(i: Intent?) {
        i?.getStringExtra("ask")?.takeIf { it.isNotBlank() }?.let { Core.ask(it); return }   // domanda già scritta (scorciatoie, test)
        i?.getStringExtra("import_provider")?.takeIf { it.isNotBlank() }?.let { importProvider(it); return }
        val assist = i?.action == Intent.ACTION_ASSIST || i?.action == Intent.ACTION_VOICE_COMMAND
        if ((assist || Prefs.listenOnOpen) && Prefs.providers.isNotEmpty()) startListening()
    }

    /** Cervello passato da fuori (es. adb dal PC): lo usa solo se l'utente conferma sull'orologio. */
    private fun importProvider(json: String) {
        val p = runCatching { Provider.from(org.json.JSONObject(json)) }.getOrNull()?.takeIf { it.baseUrl.isNotBlank() } ?: return
        Core.scope.launch {
            val host = android.net.Uri.parse(p.baseUrl).host ?: p.baseUrl
            if (Core.confirm("Usare il cervello \"${p.name}\" (${p.model}) su $host?", always = true)) {
                Prefs.upsert(p, true); Prefs.ownActive = true; Prefs.save()
                Core.detail = "Cervello: ${p.name}"
            }
        }
    }

    fun startListening() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            if (!askedMic) { askedMic = true; requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1) }
            else Core.systemDictation?.invoke()                 // la dettatura di sistema non ha bisogno del permesso
            return
        }
        Core.listen()
    }

    @Deprecated("Deprecated in Java")
    override fun onRequestPermissionsResult(code: Int, perms: Array<String>, res: IntArray) {
        super.onRequestPermissionsResult(code, perms, res)
        if (code == 1) {
            if (res.firstOrNull() == PackageManager.PERMISSION_GRANTED) Core.listen() else Core.systemDictation?.invoke()
        }
    }

    /** Schermo acceso mentre NEXUS ascolta, pensa o parla (poi torna normale). */
    fun keepAwake(on: Boolean) {
        if (on || Core.torch) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    // la torcia: schermo al massimo
    fun setTorch(on: Boolean) {
        window.attributes = window.attributes.apply { screenBrightness = if (on) 1f else WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE }
        if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
}

private val Red = Color(0xFFFF5A6E)

@Composable
private fun App() {
    val act = LocalContext.current as MainActivity
    val dictation = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        Core.onDictation(r.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull())
    }
    LaunchedEffect(Unit) { Core.systemDictation = { runCatching { dictation.launch(Core.dictationIntent()) }.onFailure { Core.state = "error"; Core.detail = "Dettatura non disponibile" } } }
    LaunchedEffect(Core.torch) { act.setTorch(Core.torch) }
    val busyNow = Core.state in setOf("listening", "thinking", "acting", "speaking") || Core.confirmText.isNotEmpty()
    LaunchedEffect(busyNow) { act.keepAwake(busyNow) }
    val nav = rememberSwipeDismissableNavController()
    MaterialTheme {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            SwipeDismissableNavHost(nav, startDestination = "home") {
                composable("home") { Home(onChat = { nav.navigate("chat") }, onSettings = { nav.navigate("settings") }) }
                composable("chat") { ChatScreen() }
                composable("settings") { SettingsScreen(onBrain = { nav.navigate("brain") }, onTailscale = { nav.navigate("tailscale") }, onAssist = { nav.navigate("assist") }) }
                composable("assist") { AssistScreen() }
                composable("tailscale") { TailscaleScreen() }
                composable("brain") { BrainScreen(onManual = { nav.navigate("manual") }) }
                composable("manual") { ManualScreen(onDone = { nav.popBackStack() }) }
            }
            if (Core.confirmText.isNotEmpty()) ConfirmOverlay()
            if (Core.torch) Box(Modifier.fillMaxSize().background(Color.White).clickable { Core.torch = false })
        }
    }
}

// ====================================================================== HOME
@Composable
private fun Home(onChat: () -> Unit, onSettings: () -> Unit) {
    val act = LocalContext.current as MainActivity
    val busy = Core.state in setOf("listening", "thinking", "acting", "speaking")
    Scaffold(timeText = { TimeText() }, vignette = { Vignette(VignettePosition.TopAndBottom) }) {
        Column(Modifier.fillMaxSize().padding(horizontal = 14.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center) {
            Spacer(Modifier.height(18.dp))
            // il "casco": visiera scura con il volto a LED; toccalo per parlare
            Box(Modifier.fillMaxWidth(0.84f).clip(RoundedCornerShape(26.dp)).background(Look.shellMid)
                .padding(5.dp).clip(RoundedCornerShape(22.dp)).background(Look.theme.glass)
                .clickable { if (busy) Core.stopAll() else act.startListening() }.padding(horizontal = 8.dp, vertical = 6.dp),
                contentAlignment = Alignment.Center) {
                DotFace(Modifier.fillMaxWidth(), cols = 21, rows = 11)
            }
            Spacer(Modifier.height(6.dp))
            val line = when {
                Prefs.providers.isEmpty() -> "Apri NEXUS sul telefono per collegarmi"
                Core.state == "idle" && Core.reply.isBlank() && Prefs.active()?.let { Ts.isTailnet(android.net.Uri.parse(it.baseUrl).host ?: "") } == true &&
                    Ts.state != "Running" -> "Il cervello è su Tailscale: ⚙ → Tailscale per collegarmi"
                Core.state == "listening" && Core.transcript.isNotBlank() -> Core.transcript
                Core.sayText.isNotBlank() && Core.state == "speaking" -> Core.sayText
                Core.reply.isNotBlank() && Core.state == "idle" -> Core.reply
                else -> Look.statusText
            }
            Text(line, color = if (Core.state == "error") Red else Color(0xFFE8ECF0), fontSize = 12.sp, textAlign = TextAlign.Center,
                maxLines = 3, overflow = TextOverflow.Ellipsis, lineHeight = 14.sp, modifier = Modifier.fillMaxWidth(0.9f).height(44.dp)
                    .clickable(enabled = Core.reply.isNotBlank()) { onChat() })
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SmallRound(Icons.Filled.Forum, "Conversazione", onChat)
                Button(onClick = { if (busy) Core.stopAll() else act.startListening() }, modifier = Modifier.size(52.dp),
                    colors = ButtonDefaults.buttonColors(backgroundColor = if (busy) Red else Look.led)) {
                    Icon(if (busy) Icons.Filled.Stop else Icons.Filled.Mic, if (busy) "Ferma" else "Parla",
                        tint = Color(0xFF0B1015), modifier = Modifier.size(26.dp))
                }
                SmallRound(Icons.Filled.Settings, "Impostazioni", onSettings)
            }
            Spacer(Modifier.height(4.dp))
        }
    }
}

@Composable
private fun SmallRound(icon: ImageVector, desc: String, onClick: () -> Unit) =
    Button(onClick = onClick, modifier = Modifier.size(36.dp), colors = ButtonDefaults.secondaryButtonColors()) {
        Icon(icon, desc, modifier = Modifier.size(18.dp))
    }

@Composable
private fun ConfirmOverlay() {
    Box(Modifier.fillMaxSize().background(Color(0xEE000000)).padding(18.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(Core.confirmText, color = Color.White, fontSize = 14.sp, textAlign = TextAlign.Center, maxLines = 5)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Button({ Core.answerConfirm(false) }, colors = ButtonDefaults.secondaryButtonColors()) { Icon(Icons.Filled.Close, "No") }
                Button({ Core.answerConfirm(true) }, colors = ButtonDefaults.buttonColors(backgroundColor = Look.led)) { Icon(Icons.Filled.Check, "Sì", tint = Color.Black) }
            }
        }
    }
}

// ====================================================================== tastiera / dettatura
@Composable
private fun rememberTextInput(label: String, onText: (String) -> Unit): () -> Unit {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        r.data?.let { RemoteInput.getResultsFromIntent(it)?.getCharSequence("t")?.toString() }?.takeIf { it.isNotBlank() }?.let(onText)
    }
    return {
        val i = RemoteInputIntentHelper.createActionRemoteInputIntent()
        RemoteInputIntentHelper.putRemoteInputsExtra(i, listOf(RemoteInput.Builder("t").setLabel(label).build()))
        launcher.launch(i)
    }
}

// ====================================================================== CHAT
@Composable
private fun ChatScreen() {
    val st = rememberScalingLazyListState(initialCenterItemIndex = 0)
    val type = rememberTextInput("Scrivi a NEXUS") { Core.ask(it) }
    LaunchedEffect(Core.chat.size) { if (Core.chat.isNotEmpty()) st.animateScrollToItem(Core.chat.size) }
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Conversazione") } }
            if (Core.chat.isEmpty()) item { Text("Ancora niente. Tocca il microfono e chiedimi qualcosa.", color = Color.Gray, fontSize = 12.sp, textAlign = TextAlign.Center) }
            items(Core.chat) { m ->
                Box(Modifier.fillMaxWidth(), contentAlignment = if (m.fromUser) Alignment.CenterEnd else Alignment.CenterStart) {
                    Text(m.text, color = if (m.fromUser) Color(0xFF0B1015) else Color.White, fontSize = 13.sp,
                        modifier = Modifier.clip(RoundedCornerShape(14.dp)).background(if (m.fromUser) Look.led else Color(0xFF22262D))
                            .padding(horizontal = 10.dp, vertical = 6.dp))
                }
            }
            item {
                Chip(onClick = type, label = { Text("Scrivi") }, colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

// ====================================================================== IMPOSTAZIONI
@Composable
private fun SettingsScreen(onBrain: () -> Unit, onTailscale: () -> Unit, onAssist: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val st = rememberScalingLazyListState()
    val bodyPerm = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Impostazioni") } }
            item {
                val p = Prefs.active()
                Chip(onClick = onBrain, label = { Text("Cervello") },
                    secondaryLabel = { Text(p?.let { "${it.name} · ${it.model}" } ?: "Nessuno", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    colors = ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black), modifier = Modifier.fillMaxWidth())
            }
            item {
                val last = if (Prefs.syncedAt > 0) "Ultima: " + SimpleDateFormat("d/M HH:mm", Locale.ITALIAN).format(Date(Prefs.syncedAt)) else "Mai ricevute"
                Chip(onClick = { scope.launch { Sync.request(ctx) } }, label = { Text("Dal telefono") },
                    secondaryLabel = { Text(Sync.status.ifBlank { last }, maxLines = 2) },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item {
                Chip(onClick = onTailscale, label = { Text("Tailscale") }, secondaryLabel = { Text(Ts.label, maxLines = 2) },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item {
                var def by remember { mutableStateOf(Assist.isDefault(ctx)) }
                LaunchedEffect(Unit) { while (true) { def = Assist.isDefault(ctx); delay(1500) } }
                Chip(onClick = onAssist, label = { Text("Al posto di Gemini") },
                    secondaryLabel = { Text(if (def) "NEXUS è l'assistente ✓" else "Tocca per mettere NEXUS", maxLines = 2) },
                    colors = if (def) ChipDefaults.secondaryChipColors() else ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black),
                    modifier = Modifier.fillMaxWidth())
            }
            item { Toggle("Leggi a voce", Prefs.speak) { Prefs.speak = it; Prefs.save() } }
            item { Toggle("Ascolta all'apertura", Prefs.listenOnOpen) { Prefs.listenOnOpen = it; Prefs.save() } }
            item { Toggle("Riascolta se chiede", Prefs.autoListen) { Prefs.autoListen = it; Prefs.save() } }
            item { Toggle("Automode", Prefs.autoMode) { Prefs.autoMode = it; Prefs.save() } }
            item {
                Chip(onClick = {
                    val i = (THEMES.indexOfFirst { it.key == Prefs.theme } + 1) % THEMES.size
                    Look.applyTheme(THEMES[i].key)
                }, label = { Text("Tema") }, secondaryLabel = { Text(Look.theme.name) },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item {
                val ok = ctx.checkSelfPermission(Manifest.permission.BODY_SENSORS) == PackageManager.PERMISSION_GRANTED
                Chip(onClick = { bodyPerm.launch(Manifest.permission.BODY_SENSORS) }, label = { Text("Battito cardiaco") },
                    secondaryLabel = { Text(if (ok) "Permesso dato" else "Tocca per dare il permesso") },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item {
                val v = runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: ""
                Text("NEXUS per Wear OS $v", color = Color.Gray, fontSize = 11.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp))
            }
        }
    }
}

@Composable
private fun Toggle(label: String, on: Boolean, onChange: (Boolean) -> Unit) =
    ToggleChip(checked = on, onCheckedChange = onChange, label = { Text(label) },
        toggleControl = { Icon(ToggleChipDefaults.switchIcon(on), if (on) "Acceso" else "Spento") },
        modifier = Modifier.fillMaxWidth())

// ====================================================================== ASSISTENTE
@Composable
private fun AssistScreen() {
    val ctx = LocalContext.current
    val st = rememberScalingLazyListState()
    var def by remember { mutableStateOf(Assist.isDefault(ctx)) }
    LaunchedEffect(Unit) { while (true) { def = Assist.isDefault(ctx); delay(1000) } }
    val role = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        def = Assist.isDefault(ctx)
        if (!def) Assist.openSettings(ctx)
    }
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Al posto di Gemini") } }
            item {
                Text(if (def) "NEXUS è l'assistente dell'orologio ✓"
                     else "Rendi NEXUS l'assistente dell'orologio: si apre e ti ascolta quando tieni premuto il tasto.",
                    color = if (def) Look.led else Color.White, fontSize = 13.sp, textAlign = TextAlign.Center)
            }
            if (!def) item {
                Chip(onClick = {
                    val i = Assist.requestIntent(ctx)
                    if (i != null) runCatching { role.launch(i) }.onFailure { Assist.openSettings(ctx) } else Assist.openSettings(ctx)
                }, label = { Text("Metti NEXUS") }, secondaryLabel = { Text("Scegli NEXUS come assistente") },
                    colors = ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black), modifier = Modifier.fillMaxWidth())
            }
            item {
                Text("Sul tasto: Impostazioni → Funzioni avanzate → Personalizza tasti → Tieni premuto → Assistente vocale.",
                    color = Color.Gray, fontSize = 11.sp, textAlign = TextAlign.Center)
            }
            item {
                Chip(onClick = { Assist.openSettings(ctx) }, label = { Text("Apri impostazioni") },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

// ====================================================================== TAILSCALE
@Composable
private fun TailscaleScreen() {
    val ctx = LocalContext.current
    val st = rememberScalingLazyListState()
    LaunchedEffect(Unit) { if (Prefs.tailscale && Ts.state == "Spento") Ts.start(ctx, "nexus-orologio") }
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Tailscale") } }
            item {
                Text(if (Ts.state == "Running") "Collegato come ${Ts.name.substringBefore('.').ifBlank { "nexus-orologio" }}\n${Ts.ip}"
                     else "Collega l'orologio alla tua rete Tailscale: raggiunge il tuo PC anche fuori casa, senza telefono.",
                    color = Color(0xFFE8ECF0), fontSize = 12.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 8.dp))
            }
            if (!Prefs.tailscale || Ts.state in setOf("Spento", "Errore")) item {
                Chip(onClick = { TsLogin.begin(ctx) }, label = { Text("Collega") }, secondaryLabel = { if (Ts.state == "Errore") Text(Ts.error.take(80), maxLines = 3) },
                    colors = ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black), modifier = Modifier.fillMaxWidth())
            }
            if (Ts.state == "Starting" || Ts.state == "NoState" || (Ts.state == "NeedsLogin" && Ts.authUrl.isBlank())) item {
                Text("Mi collego…" + if (Ts.log.isNotBlank()) "\n" + Ts.log.substringAfter(' ').take(70) else "",
                    color = Color.Gray, fontSize = 11.sp, textAlign = TextAlign.Center, maxLines = 3)
            }
            if (Ts.state == "NeedsLogin" && Ts.authUrl.isNotBlank()) {
                item {
                    Chip(onClick = { TsLogin.openOnPhone(ctx, Ts.authUrl) }, label = { Text("Apri sul telefono") },
                        secondaryLabel = { Text("Approva il login lì") },
                        colors = ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black), modifier = Modifier.fillMaxWidth())
                }
                item {
                    val bmp = remember(Ts.authUrl) { TsLogin.qr(Ts.authUrl) }
                    androidx.compose.foundation.Image(bmp.asImageBitmap(), "QR per il login",
                        modifier = Modifier.size(150.dp).clip(RoundedCornerShape(10.dp)))
                }
                item { Text("Oppure inquadra il QR", color = Color.Gray, fontSize = 11.sp) }
            }
            if (Ts.state == "NeedsMachineAuth") item { Text("Approva il dispositivo nella console di Tailscale.", color = Color.Gray, fontSize = 12.sp, textAlign = TextAlign.Center) }
            if (Ts.state == "Running") item {
                Chip(onClick = { Ts.logout(); Prefs.tailscale = false; Prefs.save() }, label = { Text("Scollega") },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

// ====================================================================== CERVELLO
@Composable
private fun BrainScreen(onManual: () -> Unit) {
    val st = rememberScalingLazyListState()
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Cervello") } }
            items(Prefs.providers) { p ->
                val on = Prefs.active()?.id == p.id
                Chip(onClick = { Prefs.activeProvider = p.id; Prefs.ownActive = true; Prefs.save() },
                    label = { Text(p.name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    secondaryLabel = { Text(p.model.ifBlank { "—" }, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    colors = if (on) ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black) else ChipDefaults.secondaryChipColors(),
                    modifier = Modifier.fillMaxWidth())
            }
            if (Prefs.providers.isEmpty()) item {
                Text("Nessun cervello. Il modo più comodo: apri NEXUS sul telefono, li manda da solo.", color = Color.Gray,
                    fontSize = 12.sp, textAlign = TextAlign.Center)
            }
            item { Chip(onClick = onManual, label = { Text("Aggiungi a mano") }, colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth()) }
        }
    }
}

@Composable
private fun ManualScreen(onDone: () -> Unit) {
    var preset by remember { mutableStateOf(PRESETS.first()) }
    var url by remember { mutableStateOf(preset.baseUrl) }
    var key by remember { mutableStateOf("") }
    var model by remember { mutableStateOf(preset.model) }
    var msg by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val inUrl = rememberTextInput("Indirizzo (URL)") { url = it.trim() }
    val inKey = rememberTextInput("Chiave API") { key = it.trim() }
    val inModel = rememberTextInput("Modello") { model = it.trim() }
    val st = rememberScalingLazyListState()
    fun draft() = Provider(name = preset.label.substringBefore(" ("), preset = preset.key, kind = preset.kind, baseUrl = url, apiKey = key, model = model)
    Scaffold(timeText = { TimeText() }, positionIndicator = { PositionIndicator(st) }) {
        ScalingLazyColumn(state = st, modifier = Modifier.fillMaxSize()) {
            item { ListHeader { Text("Nuovo cervello") } }
            item {
                Chip(onClick = {
                    preset = PRESETS[(PRESETS.indexOf(preset) + 1) % PRESETS.size]; url = preset.baseUrl; model = preset.model
                }, label = { Text("Tipo") }, secondaryLabel = { Text(preset.label, maxLines = 2) },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item { Chip(onClick = inUrl, label = { Text("Indirizzo") }, secondaryLabel = { Text(url.ifBlank { "—" }, maxLines = 1) }, colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth()) }
            if (preset.needsKey) item { Chip(onClick = inKey, label = { Text("Chiave API") }, secondaryLabel = { Text(if (key.isBlank()) "—" else "••••" + key.takeLast(4)) }, colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth()) }
            item { Chip(onClick = inModel, label = { Text("Modello") }, secondaryLabel = { Text(model.ifBlank { "—" }, maxLines = 1) }, colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth()) }
            item {
                Chip(onClick = {
                    msg = "Provo…"
                    scope.launch { runCatching { Llm.models(draft()) }.onSuccess { msg = "Connesso: ${it.size} modelli" }.onFailure { msg = "Errore: ${it.message?.take(60)}" } }
                }, label = { Text("Prova") }, secondaryLabel = { if (msg.isNotBlank()) Text(msg, maxLines = 2) },
                    colors = ChipDefaults.secondaryChipColors(), modifier = Modifier.fillMaxWidth())
            }
            item {
                Chip(onClick = { Prefs.upsert(draft(), true); Prefs.ownActive = true; Prefs.save(); onDone() }, label = { Text("Salva e usa") },
                    colors = ChipDefaults.primaryChipColors(backgroundColor = Look.led, contentColor = Color.Black), modifier = Modifier.fillMaxWidth())
            }
        }
    }
}
