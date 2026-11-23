package dev.nexus.assistant.core

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognitionService
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class ChatLine(val fromUser: Boolean, val text: String, val image: String? = null)

/** Stato condiviso + cervello + voce. Vive per tutta l'app (anche se la finestra assistente si chiude). */
object Core {
    lateinit var app: Context
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    // stato per la UI
    var state by mutableStateOf("idle")          // idle | listening | thinking | acting | speaking | error
    var detail by mutableStateOf("")
    var transcript by mutableStateOf("")
    var reply by mutableStateOf("")
    var sayText by mutableStateOf("")
    var sayProgress by mutableStateOf(0f)
    var level by mutableStateOf(0f)
    var happy by mutableStateOf(false)
    val steps = mutableStateListOf<String>()
    val chat = mutableStateListOf<ChatLine>()
    var hideRequest by mutableIntStateOf(0)
    var lastImage by mutableStateOf<String?>(null)
    var confirmText by mutableStateOf("")
    private var confirmWait: kotlinx.coroutines.CompletableDeferred<Boolean>? = null

    /** Chiede conferma (in automode risponde sì da sola). */
    suspend fun confirm(question: String): Boolean {
        if (Prefs.autoMode) { steps.add("Automode: procedo"); return true }
        val d = kotlinx.coroutines.CompletableDeferred<Boolean>()
        confirmWait = d; confirmText = question
        val ok = kotlinx.coroutines.withTimeoutOrNull(45_000) { d.await() } ?: false
        confirmText = ""; confirmWait = null
        return ok
    }
    fun answerConfirm(ok: Boolean) { confirmWait?.complete(ok) }

    private var lastPartialAt = 0L
    private var heardSpeech = false       // la finestra assistente si fa da parte quando agisce

    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var recognizer: SpeechRecognizer? = null
    private var job: Job? = null
    private var history = mutableListOf<Msg>()
    private var lastTurn = 0L
    @Volatile private var cancelled = false

    fun init(ctx: Context) {
        app = ctx.applicationContext
        tts = TextToSpeech(app) { st ->
            ttsReady = st == TextToSpeech.SUCCESS
            tts?.language = Locale.ITALIAN
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) { scope.launch { state = "speaking" } }
            override fun onRangeStart(id: String?, start: Int, end: Int, frame: Int) {
                scope.launch { if (sayText.isNotEmpty()) sayProgress = end.toFloat() / sayText.length; level = 0.55f + Math.random().toFloat() * 0.45f }
            }
            override fun onDone(id: String?) { scope.launch { afterSpeech() } }
            @Deprecated("Deprecated in Java") override fun onError(id: String?) { scope.launch { afterSpeech() } }
        })
        // la "bocca" si chiude piano tra una parola e l'altra
        scope.launch { while (isActive) { delay(50); if (level > 0f) level = (level - 0.08f).coerceAtLeast(0f) } }
    }

    // ------------------------------------------------------------ ascolto
    private fun recognizerComponent(): ComponentName? {
        val list = app.packageManager.queryIntentServices(Intent(RecognitionService.SERVICE_INTERFACE), 0)
            .map { ComponentName(it.serviceInfo.packageName, it.serviceInfo.name) }
            .filter { it.packageName != app.packageName }
        return list.firstOrNull { it.packageName == "com.google.android.googlequicksearchbox" }
            ?: list.firstOrNull { it.packageName.startsWith("com.google") } ?: list.firstOrNull()
    }

    /** Deve essere chiamato dal thread principale. */
    fun listen() {
        stopSpeaking()
        recognizer?.destroy()
        val comp = recognizerComponent()
        recognizer = if (comp != null) SpeechRecognizer.createSpeechRecognizer(app, comp) else SpeechRecognizer.createSpeechRecognizer(app)
        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(p: Bundle?) { state = "listening"; detail = "Ti ascolto"; transcript = "" }
            override fun onBeginningOfSpeech() { heardSpeech = true; lastPartialAt = System.currentTimeMillis() }
            override fun onRmsChanged(rms: Float) { level = ((rms + 2f) / 12f).coerceIn(0f, 1f) }
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEndOfSpeech() { level = 0f; state = "thinking"; detail = "Ho capito" }
            override fun onError(err: Int) {
                level = 0f
                if (state == "listening" || state == "thinking") { state = "idle"; detail = if (err == SpeechRecognizer.ERROR_NO_MATCH || err == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) "Non ho sentito niente" else "Microfono non disponibile ($err)" }
            }
            override fun onPartialResults(b: Bundle?) {
                b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let {
                    if (it != transcript) { transcript = it; lastPartialAt = System.currentTimeMillis(); heardSpeech = true }
                }
            }
            override fun onResults(b: Bundle?) {
                val text = b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                if (text.isBlank()) { state = "idle"; detail = "Non ho sentito niente"; return }
                ask(text)
            }
            override fun onEvent(t: Int, b: Bundle?) {}
        })
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 700L)
            .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 600L)
        heardSpeech = false; lastPartialAt = System.currentTimeMillis()
        recognizer?.startListening(intent)
        // sicurezza: Google a volte continua ad ascoltare il rumore; chiudiamo noi
        val myRec = recognizer
        scope.launch {
            val t0 = System.currentTimeMillis()
            while (state == "listening" && recognizer === myRec) {
                delay(200)
                val now = System.currentTimeMillis()
                if ((heardSpeech && now - lastPartialAt > 1200) || now - t0 > 15_000) { myRec?.stopListening(); break }
            }
        }
    }

    fun stopAll() {
        cancelled = true
        job?.cancel(); recognizer?.cancel(); stopSpeaking()
        state = "idle"; detail = "Fermato"; level = 0f; sayText = ""
    }

    private fun stopSpeaking() { tts?.stop(); sayText = "" }

    // ------------------------------------------------------------ voce
    private fun speak(text: String) {
        val clean = text.replace(Regex("[*_#`>|]"), "").replace(Regex("https?://\\S+"), "un link").trim()
        if (clean.isEmpty() || !ttsReady) { afterSpeech(); return }
        tts?.setPitch(Prefs.speechPitch); tts?.setSpeechRate(Prefs.speechRate)
        sayText = clean; sayProgress = 0f
        tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "nexus-" + System.currentTimeMillis())
    }

    private fun afterSpeech() {
        level = 0f; sayProgress = 1f
        val again = Prefs.autoListen && reply.trimEnd().endsWith("?") && !cancelled
        if (state == "speaking") state = "idle"
        detail = ""
        scope.launch { delay(1800); if (state == "idle") sayText = "" }
        if (again) scope.launch { delay(300); listen() }
    }

    // ------------------------------------------------------------ cervello
    private fun systemPrompt(): String {
        val now = SimpleDateFormat("EEEE d MMMM yyyy, HH:mm", Locale.ITALIAN).format(Date())
        val who = if (Prefs.userName.isNotBlank()) "di ${Prefs.userName}" else "dell'utente"
        return """Sei NEXUS, un assistente robot futuristico che vive nel telefono Android $who.
Parli SEMPRE in italiano. Le risposte vengono lette a voce: massimo 2 frasi brevi, niente elenchi, niente markdown, niente emoji.
Usa i tool per agire DAVVERO sul telefono invece di spiegare come fare. Non rispondere mai "non posso": trova un modo.
- App: open_app. Siti: open_url, web_search, youtube. Sveglie e timer: set_alarm, set_timer.
- Terminale: run_shell esegue comandi della shell Android (getprop, ls, ping, date, settings get…).
- Modalità: set_mode('auto') per non chiedere conferme, set_mode('manuale') per chiederle.
- Immagini: generate_image con un prompt dettagliato IN INGLESE (soggetto, stile, luce, inquadratura).
- Messaggi e chiamate: send_sms, whatsapp, dial (prepari tu, l'utente preme invia/chiama).
- Dentro le app: read_screen per sapere cosa c'è, poi tap_text o tap, type_text, scroll, system_button. Controlla con read_screen dopo.
NON chiudere con domande di cortesia. Fai una domanda solo se ti manca un'informazione indispensabile.
Non dire mai di aver fatto qualcosa se non hai chiamato il tool. Data e ora: $now."""
    }

    private val courtesy = Regex("(posso aiutarti|posso fare|serve altro|hai bisogno|desideri|preferisci|vuoi (che|altro|sapere|fare|provare)|cosa vuoi|altro\\?)", RegexOption.IGNORE_CASE)
    private fun dropCourtesy(r: String): String {
        val parts = r.trim().split(Regex("(?<=[.!?])\\s+")).toMutableList()
        while (parts.size > 1 && parts.last().endsWith("?") && courtesy.containsMatchIn(parts.last())) parts.removeAt(parts.size - 1)
        return parts.joinToString(" ")
    }

    fun ask(text: String) {
        job?.cancel(); cancelled = false
        quickCommand(text)?.let { r -> chat.add(ChatLine(true, text)); chat.add(ChatLine(false, r)); reply = r; transcript = text; speak(r); return }
        transcript = text; reply = ""; steps.clear(); happy = false; lastImage = null
        chat.add(ChatLine(true, text))
        state = "thinking"; detail = "Ci penso"
        job = scope.launch {
            val r = try { runAgent(text) } catch (e: kotlinx.coroutines.CancellationException) { return@launch }
                    catch (e: Exception) { state = "error"; "Non riesco a parlare con il cervello: ${e.message?.take(120)}" }
            reply = r
            chat.add(ChatLine(false, r, lastImage))
            happy = state != "error"
            scope.launch { delay(2500); happy = false }
            speak(r)
        }
    }

    /** Comandi istantanei: automode / manuale. */
    private fun quickCommand(text: String): String? {
        val t = text.lowercase()
        when {
            Regex("auto ?mode|modalit[aà] auto|automatic").containsMatchIn(t) -> Prefs.autoMode = true
            Regex("manual").containsMatchIn(t) && t.length < 60 -> Prefs.autoMode = false
            else -> return null
        }
        Prefs.save()
        return if (Prefs.autoMode) "Automode attivo: faccio tutto senza chiederti conferma." else "Modalità manuale: ti chiederò conferma prima delle cose importanti."
    }

    private suspend fun runAgent(text: String): String {
        val p = Prefs.active() ?: return "Prima aggiungi un cervello: apri NEXUS, scheda Cervello."
        if (System.currentTimeMillis() - lastTurn > 5 * 60_000) history.clear()
        lastTurn = System.currentTimeMillis()
        val tools = Tools(app, onStep = { s -> scope.launch { steps.add(s); state = "acting"; detail = s } },
            hideUi = { scope.launch { hideRequest++ } }, onImage = { path -> lastImage = path }, confirm = { q -> confirm(q) })
        val msgs = mutableListOf(Msg("system", systemPrompt())).apply { addAll(history); add(Msg("user", text)) }
        val seen = HashMap<String, Int>()
        var reply = ""
        var finished = false
        for (step in 0 until 10) {
            // tiene solo l'ultima immagine (le altre occupano troppo)
            val lastImg = msgs.indexOfLast { it.imageB64 != null }
            for (i in msgs.indices) if (i != lastImg && msgs[i].imageB64 != null) msgs[i] = msgs[i].copy(imageB64 = null, content = "(screenshot precedente)")
            val (content, calls) = withContext(Dispatchers.IO) { Llm.chat(p, msgs, tools.schemas) }
            msgs.add(Msg("assistant", content, toolCalls = calls))
            if (calls.isEmpty()) { reply = dropCourtesy(content).ifBlank { "Fatto." }; finished = true; break }
            for (c in calls) {
                val key = c.name + c.args.toString()
                seen[key] = (seen[key] ?: 0) + 1
                if (seen[key]!! > 1 && c.name !in setOf("read_screen", "look_screen", "scroll", "system_button")) {
                    msgs.add(Msg("tool", "Hai GIÀ fatto questa azione. Non ripeterla: rispondi o prova un'altra strada.", toolCallId = c.id, name = c.name))
                    continue
                }
                val res = tools.call(c.name, c.args)
                msgs.add(Msg("tool", res.text, toolCallId = c.id, name = c.name))
                if (res.imageB64 != null) msgs.add(Msg("user", "Ecco lo screenshot attuale.", imageB64 = res.imageB64))
            }
        }
        if (!finished) {
            msgs.add(Msg("system", "Basta azioni. In una frase di' cosa hai fatto e cosa manca."))
            reply = runCatching { dropCourtesy(withContext(Dispatchers.IO) { Llm.chat(p, msgs, org.json.JSONArray()) }.first) }.getOrDefault("Ho fatto il possibile, ma non ho finito.")
        }
        history = msgs.drop(1).map { it.copy(imageB64 = null, content = if (it.role == "tool") it.content.take(400) else it.content) }
            .takeLast(12).toMutableList()
        while (history.isNotEmpty() && history.first().role != "user") history.removeAt(0)
        if (state != "error") state = "idle"
        return reply
    }
}
