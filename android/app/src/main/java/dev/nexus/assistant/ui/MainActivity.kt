package dev.nexus.assistant.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.NavigationRailItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import dev.nexus.assistant.core.Core
import dev.nexus.assistant.core.Prefs
import dev.nexus.assistant.core.Provider

class MainActivity : ComponentActivity() {
    override fun onResume() {
        super.onResume()
        dev.nexus.assistant.core.WakeService.start(this)      // ascolto del nome (se acceso): si avvia con l'app davanti
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        applySetupExtras(intent)
        setContent { App() }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); applySetupExtras(intent) }

    /** Configurazione automatica via adb: am start -n dev.nexus.assistant/.ui.MainActivity --es provider_url ... */
    private fun applySetupExtras(i: Intent?) {
        i?.getStringExtra("image_url")?.let { if (i.getStringExtra("provider_url") == null) { Prefs.imageUrl = it; Prefs.save() } }
        val url = i?.getStringExtra("provider_url") ?: return
        val p = Provider(name = i.getStringExtra("provider_name") ?: "Il mio PC", preset = "ollama",
            kind = i.getStringExtra("provider_kind") ?: "ollama", baseUrl = url, model = i.getStringExtra("provider_model") ?: "qwen3.5:4b")
        Prefs.providers.firstOrNull { it.baseUrl == url }?.let { Prefs.upsert(p.copy(id = it.id), true) } ?: Prefs.upsert(p, true)
        i.getStringExtra("user_name")?.let { Prefs.userName = it; Prefs.save() }
        i.getStringExtra("image_url")?.let { Prefs.imageUrl = it; Prefs.save() }
    }

    @Composable
    private fun App() {
        val th = Look.theme
        var tab by rememberSaveable { mutableIntStateOf(0) }
        val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
        LaunchedEffect(Unit) {
            if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
                mic.launch(Manifest.permission.RECORD_AUDIO)
            dev.nexus.assistant.core.Updater.check(this@MainActivity)
            dev.nexus.assistant.core.Deps.check(this@MainActivity)
        }
        val tabs = listOf<Pair<String, ImageVector>>("NEXUS" to Icons.Filled.SmartToy, "Chat" to Icons.Filled.Forum, "Aspetto" to Icons.Filled.Palette,
            "Cervello" to Icons.Filled.Memory, "Configura" to Icons.Filled.Tune)
        BoxWithConstraints(Modifier.fillMaxSize().background(Look.bg)) {
            val tablet = maxWidth > 600.dp
            val content: @Composable (Modifier) -> Unit = { m ->
                Box(m.imePadding()) {          // in ogni scheda i campi di testo restano sopra la tastiera
                    when (tab) {
                        0 -> HomeScreen(tablet)
                        1 -> ChatsScreen(onOpen = { tab = 0 })
                        2 -> LookScreen(tablet)
                        3 -> BrainScreen()
                        else -> SetupScreen()
                    }
                }
            }
            if (tablet) {
                Row(Modifier.fillMaxSize().systemBarsPadding()) {
                    NavigationRail(containerColor = Color.Transparent) {
                        Spacer(Modifier.height(12.dp))
                        tabs.forEachIndexed { i, (label, icon) ->
                            NavigationRailItem(selected = tab == i, onClick = { tab = i }, icon = { Icon(icon, label) }, label = { Text(label) },
                                colors = NavigationRailItemDefaults.colors(selectedIconColor = Color(0xFF0B1015), indicatorColor = Look.led,
                                    unselectedIconColor = th.inkSoft, selectedTextColor = th.ink, unselectedTextColor = th.inkSoft))
                        }
                    }
                    content(Modifier.weight(1f).fillMaxHeight())
                }
            } else {
                Column(Modifier.fillMaxSize().systemBarsPadding()) {
                    content(Modifier.weight(1f).fillMaxWidth())
                    // con la tastiera aperta la barra delle schede sparisce: tutto lo spazio va a quello che scrivi
                    if (!imeOpen()) NavigationBar(containerColor = if (th.dark) Color(0xFF1C1F24) else Color.White) {
                        tabs.forEachIndexed { i, (label, icon) ->
                            NavigationBarItem(selected = tab == i, onClick = { tab = i }, icon = { Icon(icon, label) }, label = { Text(label) },
                                colors = NavigationBarItemDefaults.colors(selectedIconColor = Color(0xFF0B1015), indicatorColor = Look.led,
                                    unselectedIconColor = th.inkSoft, selectedTextColor = th.ink, unselectedTextColor = th.inkSoft))
                        }
                    }
                }
            }
        }
    }

    /** La tastiera del telefono è aperta? */
    @Composable
    private fun imeOpen(): Boolean = WindowInsets.ime.getBottom(androidx.compose.ui.platform.LocalDensity.current) > 0

    // ------------------------------------------------------------------ NEXUS
    @Composable
    private fun HomeScreen(tablet: Boolean) {
        val th = Look.theme
        val face: @Composable (Modifier) -> Unit = { m ->
            Column(m, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (dev.nexus.assistant.core.Updater.latest.isNotEmpty()) UpdateBanner()
                Helmet(Modifier.fillMaxWidth(if (tablet) .8f else .78f))
                Row(verticalAlignment = Alignment.CenterVertically) { StatusLine(); Spacer(Modifier.width(10.dp)); ModeChip() }
                if (Core.sayText.isNotEmpty())
                    Subtitle(th.ink, th.inkSoft.copy(alpha = .4f), TextStyle(fontFamily = FontFamily.Monospace, fontSize = 22.sp,
                        fontWeight = FontWeight.Bold, textAlign = TextAlign.Center), Modifier.padding(horizontal = 16.dp))
            }
        }
        val chat: @Composable (Modifier) -> Unit = { m0 ->
          Column(m0) {
            if (Core.chat.isNotEmpty()) Row(Modifier.fillMaxWidth().padding(bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(Core.chatTitle.ifBlank { "Chat" }, color = th.inkSoft, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    maxLines = 1, modifier = Modifier.weight(1f))
                Text("+ Nuova chat", color = th.ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.clip(RoundedCornerShape(50)).background(chipColor()).clickable { Core.newChat() }
                        .padding(horizontal = 12.dp, vertical = 6.dp))
            }
            val m = Modifier.weight(1f)
            val st = rememberLazyListState()
            LaunchedEffect(Core.chat.size) { if (Core.chat.isNotEmpty()) st.animateScrollToItem(Core.chat.size - 1) }
            LazyColumn(m, state = st, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(Core.chat) { line ->
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (line.fromUser) Alignment.End else Alignment.Start) {
                        Text(line.text, color = if (line.fromUser) Color(0xFF0B1015) else th.ink, fontSize = 15.sp,
                            modifier = Modifier.clip(RoundedCornerShape(18.dp))
                                .background(if (line.fromUser) Look.led else chipColor()).padding(horizontal = 14.dp, vertical = 10.dp))
                        line.image?.let { GeneratedImage(it, Modifier.padding(top = 6.dp).fillMaxWidth(.8f)) }
                    }
                }
            }
          }
        }
        if (tablet) {
            Row(Modifier.fillMaxSize().padding(24.dp).imePadding(), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Box(Modifier.weight(1.1f).fillMaxHeight(), contentAlignment = Alignment.Center) { face(Modifier.fillMaxWidth()) }
                Column(Modifier.weight(1f).fillMaxHeight()) { chat(Modifier.weight(1f)); Spacer(Modifier.height(12.dp)); ConfirmBar(); AskBar() }
            }
        } else {
            Column(Modifier.fillMaxSize().padding(16.dp).imePadding()) {
                // tastiera aperta: il casco occuperebbe tutto e il campo di testo finirebbe sotto la tastiera,
                // quindi resta solo la riga di stato e la chat con il campo sempre visibile
                if (imeOpen()) Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    StatusLine(Modifier.weight(1f)); ModeChip()
                } else face(Modifier.fillMaxWidth().padding(top = 16.dp))
                Spacer(Modifier.height(12.dp))
                chat(Modifier.weight(1f))
                Spacer(Modifier.height(10.dp))
                ConfirmBar()
                AskBar()
            }
        }
    }

    // ------------------------------------------------------------------ Configura
    @Composable
    private fun SetupScreen() {
        val th = Look.theme
        val ctx = this
        var refresh by rememberSaveable { mutableIntStateOf(0) }
        LaunchedEffect(Unit) { while (true) { kotlinx.coroutines.delay(1500); refresh++ } }
        if (refresh < 0) return
        val micOk = ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val assistOk = (Settings.Secure.getString(contentResolver, "voice_interaction_service") ?: "").contains(packageName)
        val a11yOk = dev.nexus.assistant.assist.NexusAccessibility.enabled
        val brainOk = Prefs.providers.isNotEmpty()
        val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { refresh++ }
        val cam = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { refresh++ }
        val scope = androidx.compose.runtime.rememberCoroutineScope()

        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Configura", color = th.ink, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
            Text("Quattro passi e NEXUS prende il posto di Gemini.", color = th.inkSoft)
            SetupStep("1. Microfono", "Per sentirti quando parli.", micOk, "Consenti") { mic.launch(Manifest.permission.RECORD_AUDIO) }
            SetupStep("2. Cervello", "Il tuo PC (via Tailscale o in casa) o una chiave API. Scheda Cervello.", brainOk, null) {}
            SetupStep("3. Assistente digitale", "Impostazioni → App → App predefinite → Assistente digitale → NEXUS.", assistOk, "Apri") {
                runCatching { startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)) }
                    .onFailure { startActivity(Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)) }
            }
            val camOk = ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
            SetupStep("Fotocamera", "Per \"guarda la telecamera\" e \"cosa vedi?\".", camOk, "Consenti") { cam.launch(Manifest.permission.CAMERA) }
            SetupStep("4. Accessibilità", "Serve per toccare, scrivere e leggere lo schermo nelle altre app.", a11yOk, "Apri") {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
            Text("Tasto laterale (Samsung)", color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text("Impostazioni → Funzioni avanzate → Tasto laterale → Tieni premuto → Assistente digitale. " +
                "Così tenendo premuto il tasto di spegnimento si apre NEXUS. Su Pixel e altri telefoni: Impostazioni → Sistema → Gesti → Tieni premuto il tasto di accensione.",
                color = th.inkSoft, fontSize = 14.sp)
            Text("Apri impostazioni", color = Look.led, fontWeight = FontWeight.Bold,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(chipColor())
                    .clickable { startActivity(Intent(Settings.ACTION_SETTINGS)) }.padding(horizontal = 16.dp, vertical = 10.dp))
            Text("Modalità", color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text("Manuale: chiede conferma prima di comandi e azioni importanti. Auto: fa tutto da solo (puoi anche dire “mettiti in automode”).", color = th.inkSoft, fontSize = 13.sp)
            Chips(listOf("manuale", "auto"), listOf("Manuale", "⚡ Auto"), if (Prefs.autoMode) "auto" else "manuale") { Prefs.autoMode = it == "auto"; Prefs.save() }
            Text("Immagini", color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text("Server di NEXUS sul PC (Z-Image-Turbo). Se è vuoto usa il PC del tuo cervello Ollama, oppure OpenAI.", color = th.inkSoft, fontSize = 13.sp)
            NexusField(Prefs.imageUrl, "Es. http://100.x.y.z:11434") { Prefs.imageUrl = it.trim(); Prefs.save() }
            Text("Aggiornamenti", color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Text("Versione installata: " + dev.nexus.assistant.core.Updater.current(ctx) +
                (dev.nexus.assistant.core.Updater.status.let { if (it.isBlank()) "" else " · $it" }), color = th.inkSoft, fontSize = 13.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SoftButton("Controlla") {
                    scope.launch { dev.nexus.assistant.core.Updater.check(ctx) }
                    scope.launch { dev.nexus.assistant.core.Deps.check(ctx) }
                }
                if (dev.nexus.assistant.core.Updater.latest.isNotEmpty())
                    PrimaryButton("Aggiorna a " + dev.nexus.assistant.core.Updater.latest) { scope.launch { dev.nexus.assistant.core.Updater.downloadAndInstall(ctx) } }
            }
            DepsList()
            Text("Il tuo nome (facoltativo)", color = th.ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            NexusField(Prefs.userName, "Come ti chiama NEXUS") { Prefs.userName = it; Prefs.save() }
        }
    }

    /** Attorno a NEXUS: PC (NEXUS, Ollama, modelli, programmi), Ollama senza NEXUS, orologio. */
    @Composable
    private fun DepsList() {
        val th = Look.theme
        val ctx = LocalContext.current
        val scope = androidx.compose.runtime.rememberCoroutineScope()
        val d = dev.nexus.assistant.core.Deps
        Text("Attorno a NEXUS" + if (d.checking) " · controllo…" else "", color = th.ink, fontSize = 15.sp, fontWeight = FontWeight.Bold)
        if (d.items.isEmpty() && !d.checking)
            Text("Qui compaiono Ollama e i modelli dei tuoi cervelli, NEXUS sul PC e l'app dell'orologio.", color = th.inkSoft, fontSize = 13.sp)
        d.items.forEach { it ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(chipColor()).padding(12.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(Modifier.size(9.dp).clip(RoundedCornerShape(50)).background(when (it.state) {
                    "update" -> Color(0xFFFFC857); "error" -> Color(0xFFFF5A6E); "ok" -> Look.led; else -> th.inkSoft }))
                Column(Modifier.weight(1f)) {
                    Text(it.name + (if (it.current.isNotBlank()) " · ${it.current}" else "") +
                        when { it.state == "update" && it.latest.isNotBlank() -> " → ${it.latest}"; it.state == "ok" -> " · aggiornato"; else -> "" },
                        color = th.ink, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                    val note = if (d.working == it.id && d.progress.isNotBlank()) d.progress else it.note
                    if (note.isNotBlank()) Text(note, color = if (it.state == "error") Color(0xFFFF5A6E) else th.inkSoft, fontSize = 12.sp)
                }
                if (it.action != null)
                    Text(if (d.working == it.id) "…" else "Aggiorna",
                        color = if (it.state == "update") Color(0xFF0B1015) else th.ink, fontWeight = FontWeight.Bold, fontSize = 13.sp,
                        modifier = Modifier.clip(RoundedCornerShape(50))
                            .background(if (it.state == "update") Look.led else th.bg)
                            .clickable(enabled = d.working.isEmpty() && !d.checking) { scope.launch { d.apply(ctx, it) } }
                            .padding(horizontal = 14.dp, vertical = 8.dp))
            }
        }
        if (d.working.isEmpty() && d.progress.isNotBlank())
            Text(d.progress, color = th.inkSoft, fontSize = 12.sp)
    }

    @Composable
    private fun UpdateBanner() {
        val scope = androidx.compose.runtime.rememberCoroutineScope()
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Look.led).clickable {
            scope.launch { dev.nexus.assistant.core.Updater.downloadAndInstall(this@MainActivity) } }.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text("Nuova versione ${dev.nexus.assistant.core.Updater.latest} disponibile", color = Color(0xFF0B1015),
                fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Text(if (dev.nexus.assistant.core.Updater.busy) "…" else "Aggiorna", color = Color(0xFF0B1015), fontWeight = FontWeight.ExtraBold)
        }
    }

    @Composable
    private fun SetupStep(title: String, desc: String, ok: Boolean, action: String?, onClick: () -> Unit) {
        val th = Look.theme
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(chipColor()).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, color = th.ink, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                Text(desc, color = th.inkSoft, fontSize = 13.sp)
            }
            Spacer(Modifier.width(10.dp))
            if (ok) Text("✓ Fatto", color = Color(0xFF3FB27F), fontWeight = FontWeight.Bold)
            else if (action != null) Text(action, color = Color(0xFF0B1015), fontWeight = FontWeight.Bold,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(Look.led)
                    .clickable { onClick() }.padding(horizontal = 14.dp, vertical = 8.dp))
        }
    }
}
