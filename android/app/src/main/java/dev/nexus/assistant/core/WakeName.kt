package dev.nexus.assistant.core

import java.text.Normalizer

/** Riconosce il nome dell'agente all'inizio di una frase trascritta (stessa logica del desktop, wakename.py). */
object WakeName {
    private val FILLERS = setOf("ehi", "ei", "hey", "hei", "ehy", "ok", "okay", "ciao", "senti", "oh", "o", "allora", "dai", "e",
        "il", "i", "hai", "ai", "eh", "he")

    private fun plain(text: String): List<String> =
        Normalizer.normalize(text.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9 ]+"), " ").split(" ").filter { it.isNotBlank() }

    /** Chiave fonetica semplice: Nexus ≈ Nexsus ≈ Necsus, Jarvis ≈ Giarvis. */
    private fun sound(word: String): String {
        var w = word
        for ((a, b) in listOf("ph" to "f", "gi" to "j", "ch" to "k", "ck" to "k", "qu" to "k", "x" to "ks", "y" to "i",
            "w" to "v", "c" to "k", "q" to "k", "h" to "")) w = w.replace(a, b)
        return w.replace(Regex("(.)\\1+"), "$1")
    }

    /** Somiglianza 0..1 come difflib.SequenceMatcher.ratio (blocchi comuni). */
    private fun ratio(a: String, b: String): Double {
        if (a.isEmpty() && b.isEmpty()) return 1.0
        fun matches(x: String, y: String): Int {
            if (x.isEmpty() || y.isEmpty()) return 0
            var best = 0; var bi = 0; var bj = 0
            val dp = Array(x.length + 1) { IntArray(y.length + 1) }
            for (i in 1..x.length) for (j in 1..y.length) if (x[i - 1] == y[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1] + 1
                if (dp[i][j] > best) { best = dp[i][j]; bi = i; bj = j }
            }
            if (best == 0) return 0
            return best + matches(x.substring(0, bi - best), y.substring(0, bj - best)) + matches(x.substring(bi), y.substring(bj))
        }
        return 2.0 * matches(a, b) / (a.length + b.length)
    }

    /** (trovato, resto della frase dopo il nome). */
    fun match(text: String, name: String): Pair<Boolean, String> {
        val words = plain(text); val target = plain(name)
        if (words.isEmpty() || target.isEmpty()) return false to ""
        val key = target.joinToString("") { sound(it) }
        val need = if (key.length <= 4) 0.86 else 0.78
        val n = target.size
        var i = 0
        while (i < words.size && words[i] in FILLERS && i < 3) i++
        for (start in i until minOf(i + 2, words.size)) for (size in listOf(n, n + 1, maxOf(1, n - 1))) {
            val chunk = words.subList(start, minOf(words.size, start + size))
            if (chunk.isEmpty()) continue
            if (ratio(key, chunk.joinToString("") { sound(it) }) >= need) {
                val orig = text.trim().split(Regex("\\s+"))
                return true to orig.drop(start + chunk.size).joinToString(" ").trim(' ', ',', '.', '!', '?', ';', ':')
            }
        }
        return false to ""
    }
}
