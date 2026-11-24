package dev.nexus.assistant.core

import org.junit.Assert.assertEquals
import org.junit.Test

/** Stessi casi provati sul desktop (wakename.py). */
class WakeNameTest {
    private fun m(t: String, n: String) = WakeName.match(t, n)

    @Test fun nomeConDomanda() = assertEquals(true to "che ore sono", m("Ehi Marco, che ore sono?", "Marco"))
    @Test fun soloNome() = assertEquals(true to "", m("Marco.", "Marco"))
    @Test fun nomeSimileNo() = assertEquals(false to "", m("Ehi Marta, ciao", "Marco"))
    @Test fun trascrizioneStorta() = assertEquals(true to "apri Chrome", m("Hey Nexsus apri Chrome", "Nexus"))
    @Test fun nomeAMetaFraseNo() = assertEquals(false to "", m("ieri ho visto Marco al bar", "Marco"))
    @Test fun giarvis() = assertEquals(true to "metti un timer", m("Ehi Giarvis, metti un timer", "Jarvis"))
    @Test fun nomeDueParole() = assertEquals(true to "accendi la luce", m("Ehi, Robo Uno, accendi la luce", "Robo Uno"))
    @Test fun ehiTrascrittoIl() = assertEquals(true to "che ore sono", m("Il Marco, che ore sono?", "Marco"))
    @Test fun niente() = assertEquals(false to "", m("ciao a tutti", "Ugo"))
}
