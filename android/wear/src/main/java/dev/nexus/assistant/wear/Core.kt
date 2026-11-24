package dev.nexus.assistant.wear

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONArray
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class ChatLine(val fromUser: Boolean, val text: String)

/** Stato condiviso + voce + cervello dell'orologio. */
object Core {
    lateinit var app: Context
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    var state by mutableStateOf("idle")          // idle | listening | thinking | acting | speaking | error
    var detail by mutableStateOf("")
    var transcript by mutableStateOf("")
    var reply by mutableStateOf("")
    var sayText by mutableStateOf("")
    var sayProgress by mutableStateOf(0f)
    var level by mutableStateOf(0f)
    var happy by mutableStateOf(false)
    var torch by mutableStateOf(false)
    var confirmText by mutableStateOf("")
    val chat = mutableStateListOf<ChatLine>()

    /** L'Activity imposta questo: apre la dettatura di sistema quando il riconoscimento interno non c'è. */
    var systemDictation: (() -> Unit)? = null

    private var confirmWait: CompletableDeferred<Boolean>? = null
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
            if (ttsReady) tts?.language = Locale.ITALIAN
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) { scope.launch { state = "speaking" } }
            override fun onRangeStart(id: String?, start: Int, end: Int, frame: Int) {
                scope.launch { if (sayText.isNotEmpty()) sayProgress = end.toFloat() / sayText.length; level = 0.55f + Math.random().toFloat() * 0.45f }
            }
            override fun onDone(id: String?) { scope.launch { afterSpeech() } }
            @Deprecated("Deprecated in Java") override fun onError(id: String?) { scope.launch { afterSpeech() } }
        })
        scope.launch { while (isActive) { delay(50); if (level > 0f) level = (level - 0.08f).coerceAtLeast(0f) } }
    }

    suspend fun confirm(question: String, always: Boolean = false): Boolean {
        if (Prefs.autoMode && !always) return true
        val d = CompletableDeferred<Boolean>()
        confirmWait = d; confirmText = question
        val ok = withTimeoutOrNull(40_000) { d.await() } ?: false
        confirmText = ""; confirmWait = null
        return ok
    }
    fun answerConfirm(ok: Boolean) { confirmWait?.complete(ok) }

    // ------------------------------------------------------------ ascolto
    /** Dal thread principale. Usa il riconoscimento interno se c'è, altrimenti la dettatura di sistema. */
    fun listen() {
        stopSpeaking()
        if (!SpeechRecognizer.isRecognitionAvailable(app)) { state = "listening"; detail = "Ti ascolto"; systemDictation?.invoke(); return }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(app)
        var heard = false
        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(p: Bundle?) { state = "listening"; detail = "Ti ascolto"; transcript = "" }
            override fun onBeginningOfSpeech() { heard = true }
            override fun onRmsChanged(rms: Float) { level = ((rms + 2f) / 12f).coerceIn(0f, 1f) }
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEndOfSpeech() { level = 0f; state = "thinking"; detail = "Ho capito" }
            override fun onError(err: Int) {
                level = 0f
                if (err == SpeechRecognizer.ERROR_CLIENT || err == SpeechRecognizer.ERROR_SERVER_DISCONNECTED ||
                    err == SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE || err == SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED) {
                    systemDictation?.invoke(); return              // il servizio interno non va: dettatura di sistema
                }
                if (state == "listening" || state == "thinking") {
                    state = "idle"
                    detail = if (err == SpeechRecognizer.ERROR_NO_MATCH || err == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) "Non ho sentito" else "Microfono non disponibile ($err)"
                }
            }
            override fun onPartialResults(b: Bundle?) { b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let { transcript = it } }
            override fun onResults(b: Bundle?) {
                val text = b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                if (text.isBlank()) { state = "idle"; detail = if (heard) "Non ho capito" else "Non ho sentito"; return }
                ask(text)
            }
            override fun onEvent(t: Int, b: Bundle?) {}
        })
        recognizer?.startListening(dictationIntent().putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true))
    }

    fun dictationIntent(): Intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
        .putExtra(RecognizerIntent.EXTRA_PROMPT, "Parla con NEXUS")

    /** Risultato della dettatura di sistema (null = annullata). */
    fun onDictation(text: String?) {
        if (text.isNullOrBlank()) { if (state == "listening") { state = "idle"; detail = "" }; return }
        ask(text)
    }

    fun stopAll() {
        cancelled = true
        job?.cancel(); recognizer?.cancel(); stopSpeaking()
        confirmWait?.complete(false)
        state = "idle"; detail = "Fermato"; level = 0f; sayText = ""
    }

    private fun stopSpeaking() { tts?.stop(); sayText = "" }

    // ------------------------------------------------------------ voce
    private fun speak(text: String) {
        val clean = text.replace(Regex("[*_#`>|]"), "").replace(Regex("https?://\\S+"), "un link").trim()
        sayText = clean; sayProgress = 0f
        if (clean.isEmpty() || !ttsReady || !Prefs.speak) { sayProgress = 1f; afterSpeech(); return }
        tts?.setPitch(Prefs.speechPitch); tts?.setSpeechRate(Prefs.speechRate)
        tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "nexus-" + System.currentTimeMillis())
    }

    private fun afterSpeech() {
        level = 0f; sayProgress = 1f
        val again = Prefs.autoListen && reply.trimEnd().endsWith("?") && !cancelled
        if (state == "speaking") state = "idle"
        detail = ""
        if (again) scope.launch { delay(300); listen() }
    }

    // ------------------------------------------------------------ cervello
    private fun systemPrompt(): String {
        val now = SimpleDateFormat("EEEE d MMMM yyyy, HH:mm", Locale.ITALIAN).format(Date())
        val who = if (Prefs.userName.isNotBlank()) "di ${Prefs.userName}" else "dell'utente"
        return """Sei NEXUS, un assistente robot futuristico che vive nell'orologio Wear OS $who.
Parli SEMPRE in italiano. Lo schermo è minuscolo e le risposte vengono lette a voce: UNA o DUE frasi brevissime,
niente elenchi, niente markdown, niente emoji, niente link (se servono, aprili con open_on_phone).
Usa i tool per agire DAVVERO invece di spiegare come fare:
- Domande su fatti, notizie, risultati, prezzi, orari: web_search (poi read_webpage se serve) e rispondi con i dati trovati.
- Meteo: weather. Timer, promemoria: set_timer. Sveglie: set_alarm. App dell'orologio: open_app.
- Siti e cose da leggere con calma: open_on_phone. Strade: navigate.
- Orologio: battery, heart_rate, set_volume, media, torch. Modalità: set_mode.
Non dire mai di aver fatto qualcosa se non hai chiamato il tool. Non inventare dati: se non li trovi dillo.
NON chiudere con domande di cortesia. Data e ora: $now."""
    }

    private val courtesy = Regex("(posso aiutarti|posso fare|serve altro|hai bisogno|desideri|preferisci|vuoi (che|altro|sapere|fare|provare)|cosa vuoi|altro\\?)", RegexOption.IGNORE_CASE)
    private fun dropCourtesy(r: String): String {
        val parts = r.trim().split(Regex("(?<=[.!?])\\s+")).toMutableList()
        while (parts.size > 1 && parts.last().endsWith("?") && courtesy.containsMatchIn(parts.last())) parts.removeAt(parts.size - 1)
        return parts.joinToString(" ")
    }

    fun ask(text: String) {
        job?.cancel(); cancelled = false
        transcript = text; reply = ""; happy = false
        chat.add(ChatLine(true, text))
        quickCommand(text)?.let { r -> chat.add(ChatLine(false, r)); reply = r; speak(r); return }
        state = "thinking"; detail = "Ci penso"
        job = scope.launch {
            val r = try { runAgent(text) } catch (e: kotlinx.coroutines.CancellationException) { return@launch }
                    catch (e: Exception) { state = "error"; "Non riesco a parlare con il cervello: ${e.message?.take(100)}" }
            reply = r
            chat.add(ChatLine(false, r))
            while (chat.size > 40) chat.removeAt(0)
            happy = state != "error"
            scope.launch { delay(2500); happy = false }
            speak(r)
        }
    }

    private fun quickCommand(text: String): String? {
        val t = text.lowercase()
        when {
            Regex("auto ?mode|modalit[aà] auto").containsMatchIn(t) -> Prefs.autoMode = true
            Regex("manual").containsMatchIn(t) && t.length < 60 -> Prefs.autoMode = false
            Regex("^(stop|basta|zitto|fermati)\\b").containsMatchIn(t) -> { stopAll(); return "Ok." }
            else -> return null
        }
        Prefs.save()
        return if (Prefs.autoMode) "Automode attivo." else "Modalità manuale."
    }

    private suspend fun runAgent(text: String): String {
        var p = Prefs.active() ?: return "Prima mi serve un cervello: aprimi sul telefono oppure vai nelle impostazioni."
        if (System.currentTimeMillis() - lastTurn > 5 * 60_000) history.clear()
        lastTurn = System.currentTimeMillis()
        val tools = Tools(app, onStep = { s -> scope.launch { state = "acting"; detail = s } }, confirm = { q -> confirm(q) },
            onTorch = { on -> torch = on })
        val msgs = mutableListOf(Msg("system", systemPrompt())).apply { addAll(history); add(Msg("user", text)) }
        val seen = HashMap<String, Int>()
        var reply = ""
        var finished = false
        for (step in 0 until 8) {
            val (content, calls) = try {
                withContext(Dispatchers.IO) { Llm.chat(p, msgs, tools.schemas) }
            } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) {
                val cur = p
                val fb = Prefs.providers.firstOrNull { it.id != cur.id } ?: throw e
                if (!confirm("${cur.name} non risponde. Uso ${fb.name}?")) throw e
                Prefs.activeProvider = fb.id; Prefs.save(); p = fb
                withContext(Dispatchers.IO) { Llm.chat(p, msgs, tools.schemas) }
            }
            msgs.add(Msg("assistant", content, toolCalls = calls))
            if (calls.isEmpty()) { reply = dropCourtesy(content).ifBlank { "Fatto." }; finished = true; break }
            for (c in calls) {
                val key = c.name + c.args.toString()
                seen[key] = (seen[key] ?: 0) + 1
                if (seen[key]!! > 1) {
                    msgs.add(Msg("tool", "Hai GIÀ fatto questa azione. Rispondi all'utente.", toolCallId = c.id, name = c.name)); continue
                }
                val res = tools.call(c.name, c.args)
                msgs.add(Msg("tool", res.text, toolCallId = c.id, name = c.name))
            }
        }
        if (!finished) {
            msgs.add(Msg("system", "Basta azioni. In una frase di' cosa hai trovato o fatto."))
            reply = runCatching { dropCourtesy(withContext(Dispatchers.IO) { Llm.chat(p, msgs, JSONArray()) }.first) }.getOrDefault("Non sono riuscito a finire.")
        }
        history = msgs.drop(1).map { it.copy(content = if (it.role == "tool") it.content.take(600) else it.content) }.takeLast(12).toMutableList()
        while (history.isNotEmpty() && history.first().role != "user") history.removeAt(0)
        if (state != "error") state = "idle"
        return reply
    }
}
