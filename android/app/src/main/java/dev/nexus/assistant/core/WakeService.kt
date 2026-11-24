package dev.nexus.assistant.core

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import dev.nexus.whisper.WhisperNative
import java.util.concurrent.Executors
import kotlin.math.sqrt

/**
 * Ascolto sempre attivo: quando senti il nome dell'agente ("Ehi Marco") apre NEXUS già in ascolto. Un VAD a energia raccoglie le frasi brevi e solo quelle vanno a whisper.cpp (modello base):
 * il riconoscimento lavora quando qualcuno parla, non in continuo. Il microfono viene lasciato libero
 * mentre NEXUS ascolta o parla.
 */
class WakeService : Service() {
    companion object {
        private const val TAG = "NexusWake"
        private const val RATE = 16000
        private const val CHUNK = 1280                 // 80 ms
        private const val CHANNEL = "nexus_wake"
        var running by mutableStateOf(false)
        var lastHeard by mutableStateOf("")

        /** Va chiamato con l'app in primo piano (Android non permette di aprire il microfono dallo sfondo). */
        fun start(ctx: Context) {
            if (!Prefs.wakeAlways || running) return
            if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
            if (!WhisperNative.ready(ctx)) return
            runCatching { ContextCompat.startForegroundService(ctx, Intent(ctx, WakeService::class.java)) }
                .onFailure { Log.w(TAG, "non avviato: ${it.message}") }
        }

        fun stop(ctx: Context) { ctx.stopService(Intent(ctx, WakeService::class.java)) }
    }

    @Volatile private var alive = false
    private val worker = Executors.newSingleThreadExecutor()
    @Volatile private var busy = false
    private var cool = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Ascolto del nome", NotificationManager.IMPORTANCE_MIN))
        val open = PendingIntent.getActivity(this, 0, Intent(this, dev.nexus.assistant.ui.MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("In ascolto").setContentText("Di' “Ehi ${Prefs.agentName}”").setContentIntent(open).setOngoing(true).build()
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(7, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE) else startForeground(7, n)
        } catch (e: Exception) {
            Log.w(TAG, "foreground non permesso: ${e.message}"); stopSelf(); return START_NOT_STICKY
        }
        if (!alive) { alive = true; running = true; Thread(::loop, "nexus-wake").start() }
        return START_STICKY
    }

    override fun onDestroy() { alive = false; running = false; super.onDestroy() }

    private fun nexusBusy() = Core.state != "idle" && Core.state != "error"

    private fun loop() {
        try { WhisperNative.ensure(this) } catch (e: Throwable) { Log.w(TAG, "whisper: ${e.message}"); stopSelf(); return }
        val min = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        var rec: AudioRecord? = null
        val chunk = ShortArray(CHUNK)
        val preroll = ArrayDeque<ShortArray>()
        var seg: MutableList<ShortArray>? = null
        var quiet = 0
        var noise = 300.0
        val step = CHUNK.toDouble() / RATE
        while (alive) {
            if (nexusBusy()) {                          // NEXUS sta ascoltando o parlando: microfono libero
                rec?.run { runCatching { stop(); release() } }; rec = null; seg = null
                Thread.sleep(300); continue
            }
            if (rec == null) {
                rec = try {
                    @Suppress("MissingPermission")
                    AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE, AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT, maxOf(min, CHUNK * 4)).also { it.startRecording() }
                } catch (e: Exception) { Log.w(TAG, "microfono: ${e.message}"); Thread.sleep(2000); null }
                if (rec == null) continue
            }
            val got = rec.read(chunk, 0, CHUNK)
            if (got <= 0) { Thread.sleep(50); continue }
            val c = chunk.copyOf(got)
            var sum = 0.0; for (s in c) sum += s * s.toDouble()
            val rms = sqrt(sum / c.size)
            val voice = rms > maxOf(noise * 2.5, 350.0)
            if (!voice && seg == null) noise = 0.98 * noise + 0.02 * minOf(rms, 20000.0)
            if (voice) {
                if (seg == null) seg = preroll.takeLast(3).toMutableList()
                quiet = 0
            } else if (seg != null) quiet++
            preroll.addLast(c); while (preroll.size > 10) preroll.removeFirst()
            val s = seg ?: continue
            s.add(c)
            if (quiet * step > 0.45 || s.size * step > 6.0) {
                seg = null
                val dur = (s.size - quiet) * step
                if (dur in 0.3..6.5 && !busy && System.currentTimeMillis() > cool) check(s)
            }
        }
        rec?.run { runCatching { stop(); release() } }
    }

    private fun check(parts: List<ShortArray>) {
        busy = true
        val total = parts.sumOf { it.size }
        val pcm = FloatArray(total); var k = 0
        for (p in parts) for (v in p) pcm[k++] = v / 32768f
        worker.execute {
            try {
                val name = Prefs.agentName.ifBlank { "Nexus" }
                val t0 = System.currentTimeMillis()
                val text = WhisperNative.transcribe(pcm, "it", "Ehi $name.", 4).trim()
                Log.i(TAG, "“$text” in ${System.currentTimeMillis() - t0} ms")
                val (ok, rest) = WakeName.match(text, name)
                if (ok && System.currentTimeMillis() > cool) {
                    cool = System.currentTimeMillis() + 3000
                    lastHeard = text
                    // whisper base riconosce bene il nome ma storpia il resto ("abbrichrome"): NEXUS si apre già
                    // in ascolto e la domanda la capisce il riconoscimento vocale del telefono, molto più preciso
                    wake("")
                }
            } catch (e: Throwable) { Log.w(TAG, "riconoscimento: ${e.message}") } finally { busy = false }
        }
    }

    /** Apre NEXUS: come assistente predefinito (vale anche a schermo spento), altrimenti con una notifica. */
    private fun wake(rest: String) {
        val args = Bundle().apply { if (rest.length > 2) putString("ask", rest) }
        val vis = dev.nexus.assistant.assist.NexusVoiceService.instance
        if (vis != null && runCatching { vis.showSession(args, 0) }.isSuccess) return
        val i = Intent(this, dev.nexus.assistant.ui.AssistActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .apply { if (rest.length > 2) putExtra("ask", rest) }
        val ok = Build.VERSION.SDK_INT < 29 || android.provider.Settings.canDrawOverlays(this)
        if (ok && runCatching { startActivity(i) }.isSuccess) return
        val pi = PendingIntent.getActivity(this, 1, i, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        getSystemService(NotificationManager::class.java).notify(8, Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("Mi hai chiamato?")
            .setContentText("Tocca per parlare con ${Prefs.agentName}").setContentIntent(pi).setAutoCancel(true).build())
    }
}
