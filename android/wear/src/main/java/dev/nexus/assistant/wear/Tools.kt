package dev.nexus.assistant.wear

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.provider.AlarmClock
import android.view.KeyEvent
import androidx.wear.remote.interactions.RemoteActivityHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.guava.await
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume

data class ToolResult(val text: String)

/** Le azioni che il cervello può fare dall'orologio: internet, timer, sveglie, app, salute, musica, telefono. */
class Tools(private val ctx: Context, private val onStep: (String) -> Unit, private val confirm: suspend (String) -> Boolean,
            private val onTorch: (Boolean) -> Unit) {
    private val http = OkHttpClient.Builder().proxySelector(Ts.selector).connectTimeout(12, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS).build()
    private val ua = "Mozilla/5.0 (Linux; Android 13; Wear OS) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"

    private fun fn(name: String, desc: String, props: JSONObject = JSONObject(), req: List<String> = emptyList()) =
        JSONObject().put("type", "function").put("function", JSONObject().put("name", name).put("description", desc)
            .put("parameters", JSONObject().put("type", "object").put("properties", props).put("required", JSONArray(req))))
    private fun s(d: String) = JSONObject().put("type", "string").put("description", d)
    private fun n(d: String) = JSONObject().put("type", "number").put("description", d)
    private fun b(d: String) = JSONObject().put("type", "boolean").put("description", d)
    private fun e(vararg v: String) = JSONObject().put("type", "string").put("enum", JSONArray(v.toList()))

    val schemas: JSONArray = JSONArray(listOf(
        fn("web_search", "Cerca su internet e ti restituisce i risultati (titolo, riassunto, link). Usalo per notizie, fatti, " +
            "orari, prezzi, risultati sportivi, qualsiasi cosa che non sai con certezza.", JSONObject().put("query", s("cosa cercare")), listOf("query")),
        fn("read_webpage", "Legge il testo di una pagina web (es. un link trovato con web_search).", JSONObject().put("url", s("indirizzo")), listOf("url")),
        fn("weather", "Meteo attuale e dei prossimi giorni per una città.", JSONObject().put("city", s("città, es. Milano")), listOf("city")),
        fn("set_timer", "Fa partire un timer sull'orologio (anche per i promemoria: metti il testo in label).",
            JSONObject().put("seconds", n("durata in secondi")).put("label", s("nome o promemoria")), listOf("seconds")),
        fn("set_alarm", "Imposta una sveglia sull'orologio.", JSONObject().put("hour", n("ora 0-23")).put("minute", n("minuti")).put("label", s("nome")), listOf("hour", "minute")),
        fn("open_app", "Apre un'app dell'orologio (es. Spotify, Maps, Allenamento, Meteo, Google Wallet).", JSONObject().put("name", s("nome dell'app")), listOf("name")),
        fn("open_on_phone", "Apre un sito o un link sul TELEFONO collegato (l'orologio non ha un browser).", JSONObject().put("url", s("indirizzo")), listOf("url")),
        fn("navigate", "Avvia il navigatore (Google Maps) verso un luogo.", JSONObject().put("place", s("destinazione")), listOf("place")),
        fn("battery", "Batteria dell'orologio: percentuale e se è in carica."),
        fn("heart_rate", "Misura il battito cardiaco con il sensore dell'orologio (circa 15 secondi)."),
        fn("set_volume", "Volume dell'orologio in percentuale.", JSONObject().put("percent", n("0-100")), listOf("percent")),
        fn("media", "Controlla la musica in riproduzione (sull'orologio o sul telefono).", JSONObject().put("action", e("play-pausa", "avanti", "indietro")), listOf("action")),
        fn("torch", "Torcia: accende lo schermo bianco al massimo (o lo spegne).", JSONObject().put("on", b("accesa o spenta")), listOf("on")),
        fn("set_mode", "Automode ('auto': niente conferme) o modalità manuale ('manuale').", JSONObject().put("mode", e("auto", "manuale")), listOf("mode")),
    ))

    suspend fun call(name: String, a: JSONObject): ToolResult = try {
        ToolResult(withContext(Dispatchers.IO) { run(name, a) })
    } catch (e: Exception) { ToolResult("Errore in $name: ${e.message?.take(200)}") }

    private fun start(i: Intent) { i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK); ctx.startActivity(i) }
    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")
    private fun get(url: String): String = http.newCall(Request.Builder().url(url).header("User-Agent", ua)
        .header("Accept-Language", "it-IT,it;q=0.9").build()).execute().use { r ->
        if (!r.isSuccessful) throw java.io.IOException("HTTP ${r.code}")
        r.body?.string().orEmpty()
    }
    private fun clean(html: String) = android.text.Html.fromHtml(html, android.text.Html.FROM_HTML_MODE_LEGACY).toString()
        .replace(Regex("\\s+"), " ").trim()

    private suspend fun run(name: String, a: JSONObject): String = when (name) {
        "web_search" -> search(a.getString("query"))
        "read_webpage" -> {
            var url = a.getString("url"); if (!url.contains("://")) url = "https://$url"
            onStep("Leggo ${Uri.parse(url).host}")
            val raw = get(url).replace(Regex("(?is)<(script|style|noscript|svg|nav|footer|header).*?</\\1>"), " ")
            clean(raw).take(3500).ifBlank { "(pagina vuota)" }
        }
        "weather" -> weather(a.getString("city"))
        "set_timer" -> {
            val sec = a.getDouble("seconds").toInt().coerceAtLeast(1); val label = a.optString("label")
            onStep("Timer di ${fmt(sec)}")
            start(Intent(AlarmClock.ACTION_SET_TIMER).putExtra(AlarmClock.EXTRA_LENGTH, sec)
                .putExtra(AlarmClock.EXTRA_SKIP_UI, true).apply { if (label.isNotBlank()) putExtra(AlarmClock.EXTRA_MESSAGE, label) })
            "Timer di ${fmt(sec)} avviato${if (label.isNotBlank()) " ($label)" else ""}."
        }
        "set_alarm" -> {
            val h = a.getInt("hour"); val m = a.optInt("minute", 0)
            onStep("Sveglia alle %02d:%02d".format(h, m))
            start(Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR, h).putExtra(AlarmClock.EXTRA_MINUTES, m)
                .putExtra(AlarmClock.EXTRA_SKIP_UI, true).apply { a.optString("label").takeIf { it.isNotBlank() }?.let { putExtra(AlarmClock.EXTRA_MESSAGE, it) } })
            "Sveglia impostata alle %02d:%02d.".format(h, m)
        }
        "open_app" -> openApp(a.getString("name"))
        "open_on_phone" -> {
            var url = a.getString("url"); if (!url.contains("://")) url = "https://$url"
            onStep("Apro sul telefono")
            RemoteActivityHelper(ctx).startRemoteActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))
                .addCategory(Intent.CATEGORY_BROWSABLE)).await()
            "Ho aperto il link sul telefono."
        }
        "navigate" -> {
            val place = a.getString("place"); onStep("Navigatore verso $place")
            val i = Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=${enc(place)}"))
            if (i.resolveActivity(ctx.packageManager) != null) { start(i); "Navigatore avviato verso $place." }
            else {
                RemoteActivityHelper(ctx).startRemoteActivity(Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=${enc(place)}"))
                    .addCategory(Intent.CATEGORY_BROWSABLE)).await()
                "Sull'orologio non c'è Maps: ho avviato il navigatore sul telefono."
            }
        }
        "battery" -> {
            val bm = ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            "Batteria al ${bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)}%${if (bm.isCharging) ", in carica" else ""}."
        }
        "heart_rate" -> heartRate()
        "set_volume" -> {
            val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val p = a.getDouble("percent").toInt().coerceIn(0, 100)
            am.setStreamVolume(AudioManager.STREAM_MUSIC, am.getStreamMaxVolume(AudioManager.STREAM_MUSIC) * p / 100, 0)
            onStep("Volume $p%"); "Volume al $p%."
        }
        "media" -> {
            val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val code = when (a.getString("action")) { "avanti" -> KeyEvent.KEYCODE_MEDIA_NEXT; "indietro" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS; else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE }
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code)); am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
            onStep("Musica: ${a.getString("action")}"); "Fatto."
        }
        "torch" -> { val on = a.optBoolean("on", true); withContext(Dispatchers.Main) { onTorch(on) }; if (on) "Torcia accesa: tocca lo schermo per spegnerla." else "Torcia spenta." }
        "set_mode" -> {
            val on = a.getString("mode") == "auto"
            withContext(Dispatchers.Main) { Prefs.autoMode = on; Prefs.save() }
            if (on) "Automode attivo: niente più conferme." else "Modalità manuale: ti chiederò conferma."
        }
        else -> "Tool sconosciuto: $name"
    }

    private fun fmt(sec: Int) = when {
        sec % 3600 == 0 -> "${sec / 3600} ore"; sec >= 3600 -> "${sec / 3600} h ${(sec % 3600) / 60} min"
        sec % 60 == 0 -> "${sec / 60} minuti"; sec > 60 -> "${sec / 60} min ${sec % 60} s"; else -> "$sec secondi"
    }

    /** DuckDuckGo (versione HTML, niente chiavi); se non risponde, Wikipedia in italiano. */
    private fun search(q: String): String {
        onStep("Cerco: $q")
        val out = StringBuilder()
        runCatching {
            val html = get("https://html.duckduckgo.com/html/?q=${enc(q)}&kl=it-it")
            val links = Regex("<a[^>]+class=\"result__a\"[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", RegexOption.DOT_MATCHES_ALL).findAll(html).toList()
            val snips = Regex("class=\"result__snippet\"[^>]*>(.*?)</a>", RegexOption.DOT_MATCHES_ALL).findAll(html).map { clean(it.groupValues[1]) }.toList()
            links.take(6).forEachIndexed { i, m ->
                var url = m.groupValues[1]
                Regex("uddg=([^&]+)").find(url)?.let { url = URLDecoder.decode(it.groupValues[1], "UTF-8") }
                out.append("${i + 1}. ${clean(m.groupValues[2])} — ${snips.getOrElse(i) { "" }} ($url)\n")
            }
        }
        if (out.isEmpty()) runCatching {
            val j = JSONObject(get("https://it.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=4&srsearch=${enc(q)}"))
            val arr = j.getJSONObject("query").getJSONArray("search")
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                out.append("${i + 1}. ${r.getString("title")} — ${clean(r.getString("snippet"))} (https://it.wikipedia.org/wiki/${enc(r.getString("title").replace(' ', '_'))})\n")
            }
        }
        return out.toString().ifBlank { "Nessun risultato per '$q'." }
    }

    /** Open-Meteo: gratis e senza chiave. */
    private fun weather(city: String): String {
        onStep("Meteo di $city")
        val g = JSONObject(get("https://geocoding-api.open-meteo.com/v1/search?count=1&language=it&name=${enc(city)}"))
        val r = g.optJSONArray("results")?.optJSONObject(0) ?: return "Non trovo la città $city."
        val w = JSONObject(get("https://api.open-meteo.com/v1/forecast?latitude=${r.getDouble("latitude")}&longitude=${r.getDouble("longitude")}" +
            "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m" +
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=3"))
        val c = w.getJSONObject("current"); val d = w.getJSONObject("daily")
        val sb = StringBuilder("${r.getString("name")}: ora ${c.getDouble("temperature_2m")}°C (percepiti ${c.getDouble("apparent_temperature")}°C), " +
            "${wmo(c.getInt("weather_code"))}, vento ${c.getDouble("wind_speed_10m")} km/h, umidità ${c.getInt("relative_humidity_2m")}%.")
        val days = listOf("Oggi", "Domani", "Dopodomani")
        for (i in 0 until d.getJSONArray("time").length()) sb.append(" ${days[i]}: ${wmo(d.getJSONArray("weather_code").getInt(i))}, " +
            "${d.getJSONArray("temperature_2m_min").getDouble(i)}-${d.getJSONArray("temperature_2m_max").getDouble(i)}°C, " +
            "pioggia ${d.getJSONArray("precipitation_probability_max").optInt(i)}%.")
        return sb.toString()
    }

    private fun wmo(c: Int) = when (c) {
        0 -> "sereno"; 1, 2 -> "poco nuvoloso"; 3 -> "nuvoloso"; 45, 48 -> "nebbia"; in 51..57 -> "pioggerella"
        in 61..67 -> "pioggia"; in 71..77 -> "neve"; in 80..82 -> "rovesci"; 85, 86 -> "rovesci di neve"; in 95..99 -> "temporale"; else -> "variabile"
    }

    private fun openApp(q: String): String {
        val pm = ctx.packageManager
        val apps = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .map { it.loadLabel(pm).toString() to it.activityInfo.packageName }
        val want = q.lowercase().trim()
        val best = apps.firstOrNull { it.first.lowercase() == want } ?: apps.firstOrNull { it.first.lowercase().startsWith(want) }
            ?: apps.firstOrNull { it.first.lowercase().contains(want) } ?: apps.firstOrNull { want.contains(it.first.lowercase()) }
            ?: return "Non trovo l'app '$q'. App sull'orologio: ${apps.joinToString(", ") { it.first }.take(600)}"
        onStep("Apro ${best.first}")
        start(pm.getLaunchIntentForPackage(best.second) ?: return "Non riesco ad aprire ${best.first}.")
        return "Ho aperto ${best.first}."
    }

    private suspend fun heartRate(): String {
        if (ctx.checkSelfPermission(android.Manifest.permission.BODY_SENSORS) != PackageManager.PERMISSION_GRANTED)
            return "Mi serve il permesso per i sensori del corpo: aprilo da Impostazioni NEXUS sull'orologio (Battito)."
        val sm = ctx.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        val sensor = sm.getDefaultSensor(Sensor.TYPE_HEART_RATE) ?: return "Questo orologio non ha il sensore del battito."
        onStep("Misuro il battito… tieni fermo il polso")
        val values = mutableListOf<Float>()
        withTimeoutOrNull(20_000) {
            suspendCancellableCoroutine { cont ->
                val l = object : SensorEventListener {
                    override fun onSensorChanged(e: SensorEvent) {
                        if (e.values[0] > 30) values += e.values[0]
                        if (values.size >= 8 && cont.isActive) { sm.unregisterListener(this); cont.resume(Unit) }
                    }
                    override fun onAccuracyChanged(s: Sensor?, a: Int) {}
                }
                sm.registerListener(l, sensor, SensorManager.SENSOR_DELAY_NORMAL)
                cont.invokeOnCancellation { sm.unregisterListener(l) }
            }
        }
        if (values.isEmpty()) return "Non sono riuscito a leggere il battito: stringi un po' il cinturino e riprova."
        return "Battito: ${values.takeLast(5).average().toInt()} battiti al minuto."
    }
}
