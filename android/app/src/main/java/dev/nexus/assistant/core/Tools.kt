package dev.nexus.assistant.core

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.provider.AlarmClock
import android.provider.Settings
import dev.nexus.assistant.assist.NexusAccessibility
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

data class ToolResult(val text: String, val imageB64: String? = null)

/** Le azioni che il cervello può fare sul telefono. */
class Tools(private val ctx: Context, private val onStep: (String) -> Unit, private val hideUi: () -> Unit,
            private val onImage: (String) -> Unit = {}, private val confirm: suspend (String) -> Boolean = { true }) {

    // ------------------------------------------------------------ schema per il modello
    private fun fn(name: String, desc: String, props: JSONObject = JSONObject(), req: List<String> = emptyList()) =
        JSONObject().put("type", "function").put("function", JSONObject().put("name", name).put("description", desc)
            .put("parameters", JSONObject().put("type", "object").put("properties", props).put("required", JSONArray(req))))

    private fun s(desc: String) = JSONObject().put("type", "string").put("description", desc)
    private fun n(desc: String) = JSONObject().put("type", "number").put("description", desc)
    private fun e(vararg v: String) = JSONObject().put("type", "string").put("enum", JSONArray(v.toList()))

    val schemas: JSONArray = JSONArray(listOf(
        fn("open_app", "Apre un'app installata sul telefono (es. WhatsApp, Instagram, Spotify, Fotocamera).",
            JSONObject().put("name", s("nome dell'app")), listOf("name")),
        fn("open_url", "Apre un sito nel browser.", JSONObject().put("url", s("indirizzo")), listOf("url")),
        fn("web_search", "Cerca qualcosa su Google.", JSONObject().put("query", s("cosa cercare")), listOf("query")),
        fn("youtube", "Cerca o fa partire un video su YouTube.", JSONObject().put("query", s("cosa cercare")), listOf("query")),
        fn("set_alarm", "Imposta una sveglia.", JSONObject().put("hour", n("ora 0-23")).put("minute", n("minuti")).put("label", s("nome")), listOf("hour", "minute")),
        fn("set_timer", "Fa partire un timer.", JSONObject().put("seconds", n("durata in secondi")).put("label", s("nome")), listOf("seconds")),
        fn("dial", "Prepara una chiamata a un numero (l'utente preme chiama).", JSONObject().put("number", s("numero")), listOf("number")),
        fn("send_sms", "Prepara un SMS (l'utente preme invia).", JSONObject().put("number", s("numero")).put("text", s("testo")), listOf("text")),
        fn("whatsapp", "Prepara un messaggio WhatsApp a un numero (con prefisso, es. 39...).",
            JSONObject().put("number", s("numero con prefisso internazionale")).put("text", s("testo")), listOf("text")),
        fn("navigate", "Avvia il navigatore verso un luogo.", JSONObject().put("place", s("destinazione")), listOf("place")),
        fn("flashlight", "Accende o spegne la torcia.", JSONObject().put("on", JSONObject().put("type", "boolean")), listOf("on")),
        fn("set_volume", "Imposta il volume dei media in percentuale.", JSONObject().put("percent", n("0-100")), listOf("percent")),
        fn("battery", "Livello della batteria e se è in carica."),
        fn("do_not_disturb", "Attiva o disattiva la modalità Non disturbare.", JSONObject().put("on", JSONObject().put("type", "boolean")), listOf("on")),
        fn("ringer", "Suoneria: normale, vibrazione o silenzioso.", JSONObject().put("mode", e("normale", "vibrazione", "silenzioso")), listOf("mode")),
        fn("phone_brightness", "Luminosità dello schermo del telefono in percentuale (o automatica).",
            JSONObject().put("percent", n("0-100")).put("auto", JSONObject().put("type", "boolean"))),
        fn("auto_rotate", "Attiva o disattiva la rotazione automatica dello schermo.", JSONObject().put("on", JSONObject().put("type", "boolean")), listOf("on")),
        fn("quick_setting", "Tocca un interruttore delle impostazioni rapide (es. Wi-Fi, Bluetooth, Modalità aereo, Hotspot mobile, " +
            "Posizione, Risparmio energetico, NFC, Dati mobili, Modalità notte).", JSONObject().put("tile", s("nome dell'interruttore")), listOf("tile")),
        fn("look_camera", "Guarda con la fotocamera del telefono (frontale = verso l'utente, posteriore = davanti al telefono) e ti mostra la foto.",
            JSONObject().put("camera", e("frontale", "posteriore")).put("question", s("cosa guardare")), listOf("camera")),
        fn("run_shell", "Esegue un comando nella shell del telefono (sandbox dell'app: getprop, ls, ping, date, df, settings get, ecc). Ritorna l'output.",
            JSONObject().put("command", s("comando sh")), listOf("command")),
        fn("set_mode", "Automode ('auto': niente conferme) o modalità manuale ('manuale').", JSONObject().put("mode", e("auto", "manuale")), listOf("mode")),
        fn("generate_image", "Crea un'immagine da una descrizione e la salva nella Galleria. Scrivi il prompt in inglese, dettagliato.",
            JSONObject().put("prompt", s("descrizione dettagliata in inglese")).put("shape", e("quadrata", "verticale", "orizzontale")), listOf("prompt")),
        fn("open_settings", "Apre una pagina delle impostazioni.",
            JSONObject().put("page", e("wifi", "bluetooth", "schermo", "suono", "batteria", "app", "posizione", "generale")), listOf("page")),
        fn("read_screen", "Legge i testi e i pulsanti sullo schermo con la loro posizione [x,y] (0-1000)."),
        fn("look_screen", "Fa uno screenshot e te lo mostra (per capire immagini o layout)."),
        fn("tap_text", "Tocca un pulsante o una scritta sullo schermo cercandola per testo.", JSONObject().put("text", s("scritta")), listOf("text")),
        fn("tap", "Tocca un punto dello schermo (coordinate 0-1000).", JSONObject().put("x", n("0-1000")).put("y", n("0-1000"))
            .put("long", JSONObject().put("type", "boolean").put("description", "pressione lunga")), listOf("x", "y")),
        fn("type_text", "Scrive testo nel campo selezionato (o nel primo campo di testo).", JSONObject().put("text", s("testo"))
            .put("send", JSONObject().put("type", "boolean").put("description", "premi invio dopo")), listOf("text")),
        fn("scroll", "Scorre lo schermo.", JSONObject().put("direction", e("su", "giu", "sinistra", "destra")), listOf("direction")),
        fn("system_button", "Tasti di sistema.", JSONObject().put("button", e("indietro", "home", "recenti", "notifiche", "impostazioni_rapide", "blocca", "screenshot")), listOf("button")),
    ))

    // ------------------------------------------------------------ esecuzione
    private fun start(i: Intent) { i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK); ctx.startActivity(i) }
    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")
    private fun a11y(): NexusAccessibility? = NexusAccessibility.instance
    private val needA11y = "Per farlo serve attivare NEXUS in Impostazioni → Accessibilità → App installate → NEXUS."

    private fun findApp(query: String): Pair<String, String>? {
        val pm = ctx.packageManager
        val launch = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = pm.queryIntentActivities(launch, PackageManager.MATCH_ALL)
            .map { it.loadLabel(pm).toString() to it.activityInfo.packageName }
        val q = query.lowercase().trim()
        return apps.firstOrNull { it.first.lowercase() == q }
            ?: apps.firstOrNull { it.first.lowercase().startsWith(q) }
            ?: apps.firstOrNull { it.first.lowercase().contains(q) }
            ?: apps.firstOrNull { it.second.lowercase().contains(q.replace(" ", "")) }
    }

    suspend fun call(name: String, a: JSONObject): ToolResult = try { exec(name, a) } catch (e: ActivityNotFoundException) {
        ToolResult("Non c'è un'app che possa farlo.")
    } catch (e: Exception) { ToolResult("Errore in $name: ${e.message}") }

    private suspend fun exec(name: String, a: JSONObject): ToolResult {
        when (name) {
            "open_app" -> {
                val (label, pkg) = findApp(a.optString("name")) ?: return ToolResult("Non trovo l'app '${a.optString("name")}'.")
                onStep("Apro $label"); hideUi()
                start(ctx.packageManager.getLaunchIntentForPackage(pkg)!!)
                return ToolResult("Ho aperto $label.")
            }
            "open_url" -> {
                var u = a.optString("url"); if (!u.contains("://")) u = "https://$u"
                onStep("Apro $u"); hideUi(); start(Intent(Intent.ACTION_VIEW, Uri.parse(u)))
                return ToolResult("Ho aperto $u.")
            }
            "web_search" -> {
                val q = a.optString("query"); onStep("Cerco: $q"); hideUi()
                start(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com/search?q=${enc(q)}")))
                return ToolResult("Ho cercato '$q'.")
            }
            "youtube" -> {
                val q = a.optString("query"); onStep("YouTube: $q"); hideUi()
                start(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.youtube.com/results?search_query=${enc(q)}")))
                return ToolResult("Ho cercato '$q' su YouTube.")
            }
            "set_alarm" -> {
                val h = a.optInt("hour"); val m = a.optInt("minute")
                onStep("Sveglia alle %02d:%02d".format(h, m))
                start(Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR, h).putExtra(AlarmClock.EXTRA_MINUTES, m)
                    .putExtra(AlarmClock.EXTRA_MESSAGE, a.optString("label", "NEXUS")).putExtra(AlarmClock.EXTRA_SKIP_UI, true))
                return ToolResult("Sveglia impostata alle %02d:%02d.".format(h, m))
            }
            "set_timer" -> {
                val sec = a.optInt("seconds"); onStep("Timer di ${sec / 60} min ${sec % 60} s")
                start(Intent(AlarmClock.ACTION_SET_TIMER).putExtra(AlarmClock.EXTRA_LENGTH, sec)
                    .putExtra(AlarmClock.EXTRA_MESSAGE, a.optString("label", "NEXUS")).putExtra(AlarmClock.EXTRA_SKIP_UI, true))
                return ToolResult("Timer avviato.")
            }
            "dial" -> {
                onStep("Chiamata a ${a.optString("number")}"); hideUi()
                start(Intent(Intent.ACTION_DIAL, Uri.parse("tel:${a.optString("number")}")))
                return ToolResult("Ho preparato la chiamata: premi il tasto verde.")
            }
            "send_sms" -> {
                onStep("SMS"); hideUi()
                start(Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:${a.optString("number")}")).putExtra("sms_body", a.optString("text")))
                return ToolResult("Ho preparato l'SMS: premi invia.")
            }
            "whatsapp" -> {
                onStep("WhatsApp"); hideUi()
                val num = a.optString("number").filter { it.isDigit() }
                start(Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/$num?text=${enc(a.optString("text"))}")))
                // in automode lo invia anche, se l'accessibilità è attiva
                if (dev.nexus.assistant.core.Prefs.autoMode && a11y() != null) {
                    delay(3000)
                    val sent = a11y()?.clickText("Invia") ?: a11y()?.clickText("Send")
                    if (sent != null) return ToolResult("Messaggio WhatsApp inviato.")
                }
                return ToolResult("Ho aperto WhatsApp con il messaggio pronto: premi invia.")
            }
            "navigate" -> {
                val p = a.optString("place"); onStep("Navigatore: $p"); hideUi()
                start(Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=${enc(p)}")))
                return ToolResult("Navigazione verso $p avviata.")
            }
            "flashlight" -> {
                val on = a.optBoolean("on", true)
                val cm = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
                cm.setTorchMode(cm.cameraIdList.first(), on)
                onStep(if (on) "Torcia accesa" else "Torcia spenta")
                return ToolResult(if (on) "Torcia accesa." else "Torcia spenta.")
            }
            "set_volume" -> {
                val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                val max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                val p = a.optInt("percent").coerceIn(0, 100)
                am.setStreamVolume(AudioManager.STREAM_MUSIC, max * p / 100, 0)
                onStep("Volume $p%"); return ToolResult("Volume al $p%.")
            }
            "generate_image" -> {
                onStep("Creo l'immagine (può volerci un minuto)")
                val path = Images.generate(ctx, a.optString("prompt"), a.optString("shape", "quadrata"))
                onImage(path)
                return ToolResult("Immagine creata e salvata nella Galleria (cartella NEXUS).")
            }
            "do_not_disturb" -> {
                val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
                if (!nm.isNotificationPolicyAccessGranted) {
                    hideUi(); start(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS))
                    return ToolResult("Serve il permesso 'Accesso Non disturbare' per NEXUS: l'ho aperto, attivalo.")
                }
                val on = a.optBoolean("on", true)
                nm.setInterruptionFilter(if (on) android.app.NotificationManager.INTERRUPTION_FILTER_PRIORITY else android.app.NotificationManager.INTERRUPTION_FILTER_ALL)
                onStep(if (on) "Non disturbare attivo" else "Non disturbare spento")
                return ToolResult(if (on) "Non disturbare attivato." else "Non disturbare disattivato.")
            }
            "ringer" -> {
                val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
                val mode = when (a.optString("mode")) { "vibrazione" -> AudioManager.RINGER_MODE_VIBRATE; "silenzioso" -> AudioManager.RINGER_MODE_SILENT; else -> AudioManager.RINGER_MODE_NORMAL }
                return try { am.ringerMode = mode; onStep("Suoneria: ${a.optString("mode")}"); ToolResult("Suoneria: ${a.optString("mode")}.") }
                catch (e: SecurityException) { ToolResult("Per il silenzioso serve il permesso 'Accesso Non disturbare'.") }
            }
            "phone_brightness" -> {
                if (!Settings.System.canWrite(ctx)) {
                    hideUi(); start(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:${ctx.packageName}")))
                    return ToolResult("Serve il permesso 'Modifica impostazioni di sistema': l'ho aperto, attivalo.")
                }
                val cr = ctx.contentResolver
                if (a.optBoolean("auto", false)) {
                    Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_AUTOMATIC)
                    onStep("Luminosità automatica"); return ToolResult("Luminosità automatica.")
                }
                val p = a.optInt("percent", 50).coerceIn(1, 100)
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS, (p * 255 / 100).coerceAtLeast(1))
                onStep("Luminosità $p%"); return ToolResult("Luminosità al $p%.")
            }
            "auto_rotate" -> {
                if (!Settings.System.canWrite(ctx)) return ToolResult("Serve il permesso 'Modifica impostazioni di sistema'.")
                val on = a.optBoolean("on", true)
                Settings.System.putInt(ctx.contentResolver, Settings.System.ACCELEROMETER_ROTATION, if (on) 1 else 0)
                onStep(if (on) "Rotazione automatica attiva" else "Rotazione bloccata"); return ToolResult("Fatto.")
            }
            "quick_setting" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                val tile = a.optString("tile")
                hideUi(); delay(300); onStep("Impostazioni rapide: $tile")
                s.global("impostazioni_rapide"); delay(900)
                var hit = s.clickText(tile)
                if (hit == null) { s.swipe("giu"); delay(700); hit = s.clickText(tile) }     // pannello completo
                delay(600); s.global("indietro"); delay(200); s.global("indietro")
                return if (hit != null) ToolResult("Ho toccato '$hit' nelle impostazioni rapide.") else ToolResult("Non trovo '$tile' nelle impostazioni rapide.")
            }
            "look_camera" -> {
                val front = a.optString("camera", "frontale") != "posteriore"
                if (androidx.core.content.ContextCompat.checkSelfPermission(ctx, android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
                    return ToolResult("Serve il permesso della fotocamera: NEXUS → Configura → Fotocamera.")
                onStep(if (front) "Guardo con la fotocamera frontale" else "Guardo con la fotocamera posteriore")
                val img = Cam.captureB64(ctx, front)
                return ToolResult("Ecco la foto appena scattata (${if (front) "frontale" else "posteriore"}). Descrivi cosa vedi.", img)
            }
            "run_shell" -> {
                val cmd = a.optString("command")
                if (Regex("""\brm\s+-[a-z]*r|\bmkfs|\bdd\s+.*of=/dev""").containsMatchIn(cmd)) return ToolResult("Comando bloccato: troppo pericoloso.")
                onStep("Terminale: ${cmd.take(40)}")
                if (!confirm("Posso eseguire: $cmd ?")) return ToolResult("L'utente non ha dato il permesso.")
                val out = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    val p = ProcessBuilder("sh", "-c", cmd).redirectErrorStream(true).start()
                    val done = p.waitFor(60, java.util.concurrent.TimeUnit.SECONDS)
                    val text = p.inputStream.bufferedReader().readText()
                    if (!done) { p.destroyForcibly(); "$text\n(interrotto dopo 60 s)" } else "exit ${p.exitValue()}\n$text"
                }
                return ToolResult(out.takeLast(3000).ifBlank { "(nessun output)" })
            }
            "set_mode" -> {
                dev.nexus.assistant.core.Prefs.autoMode = a.optString("mode") == "auto"; dev.nexus.assistant.core.Prefs.save()
                onStep(if (dev.nexus.assistant.core.Prefs.autoMode) "Automode attivo" else "Modalità manuale")
                return ToolResult(if (dev.nexus.assistant.core.Prefs.autoMode) "Automode attivo." else "Modalità manuale.")
            }
            "battery" -> {
                val bm = ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
                val lvl = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                onStep("Batteria"); return ToolResult("Batteria al $lvl%${if (bm.isCharging) ", in carica" else ""}.")
            }
            "open_settings" -> {
                val action = when (a.optString("page")) {
                    "wifi" -> Settings.ACTION_WIFI_SETTINGS; "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
                    "schermo" -> Settings.ACTION_DISPLAY_SETTINGS; "suono" -> Settings.ACTION_SOUND_SETTINGS
                    "batteria" -> Intent.ACTION_POWER_USAGE_SUMMARY; "app" -> Settings.ACTION_APPLICATION_SETTINGS
                    "posizione" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS; else -> Settings.ACTION_SETTINGS
                }
                onStep("Impostazioni"); hideUi(); start(Intent(action))
                return ToolResult("Ho aperto le impostazioni.")
            }
            "read_screen" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                onStep("Leggo lo schermo"); hideUi(); delay(450)
                return ToolResult("Schermo (posizioni 0-1000):\n" + s.describeScreen())
            }
            "look_screen" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                onStep("Guardo lo schermo"); hideUi(); delay(500)
                val img = s.screenshotB64() ?: return ToolResult("Screenshot non disponibile. Testi:\n" + s.describeScreen())
                return ToolResult("Ecco lo schermo. Testi e posizioni:\n" + s.describeScreen(1200), img)
            }
            "tap_text" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                hideUi(); delay(350); onStep("Tocco “${a.optString("text")}”")
                val hit = s.clickText(a.optString("text")) ?: return ToolResult("Non vedo '${a.optString("text")}' sullo schermo.")
                delay(600); return ToolResult("Ho toccato '$hit'.")
            }
            "tap" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                hideUi(); delay(350); onStep("Tocco lo schermo")
                s.tap(a.optDouble("x").toFloat(), a.optDouble("y").toFloat(), a.optBoolean("long", false))
                delay(600); return ToolResult("Fatto.")
            }
            "type_text" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                hideUi(); delay(300); onStep("Scrivo “${a.optString("text").take(30)}”")
                if (!s.typeText(a.optString("text"))) return ToolResult("Non trovo un campo di testo: prima tocca il campo giusto.")
                if (a.optBoolean("send", false)) { delay(300); s.clickText("Invia") ?: s.clickText("Send") }
                return ToolResult("Testo scritto.")
            }
            "scroll" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                hideUi(); delay(300); onStep("Scorro"); s.swipe(a.optString("direction", "su")); delay(500)
                return ToolResult("Fatto.")
            }
            "system_button" -> {
                val s = a11y() ?: return ToolResult(needA11y)
                hideUi(); delay(250); onStep("Tasto ${a.optString("button")}"); s.global(a.optString("button"))
                return ToolResult("Fatto.")
            }
        }
        return ToolResult("Azione sconosciuta: $name")
    }
}
