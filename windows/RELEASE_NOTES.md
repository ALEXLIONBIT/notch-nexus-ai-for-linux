**Novità 0.4.0** — **Dagli il nome che vuoi**: Personalizza → Ascolto → *Come si chiama* (es. Marco) e scegli *Ehi Marco* come parola per svegliarlo. Puoi anche dire tutto di fila: “Marco, che tempo fa domani?”. Si presenta col suo nome. La prima volta scarica un piccolo modello (75 MB).

**Novità 0.3.0**
- **Chat**: pulsante 💬 nel notch → finestra con tutte le conversazioni salvate: cerca, riapri (NEXUS ricorda il discorso), nuova chat, elimina; scrivi o parla da lì
- **Modelli**: Personalizza → Modelli → cerca nel catalogo di Ollama, scarica con la barra di avanzamento, usa o elimina. Le taglie in azzurro entrano nella scheda video. Anche a voce: "installa qwen3 da 4b e usalo"

Prima versione di **NEXUS per Windows 10/11**: lo stesso robot del PC Linux, con notch in alto, casco a LED e voce.

**Installazione:** scarica `NEXUS-Setup-*.exe` e aprilo. Non servono permessi da amministratore. Windows potrebbe
mostrare "PC protetto da Windows" perché l'app non è firmata: clicca *Ulteriori informazioni → Esegui comunque*.

Al primo avvio scegli dove ragiona il robot:
- **Su questo PC**: NEXUS installa Ollama e scarica il cervello giusto per la tua scheda video
- **Con un provider**: il tuo PC di casa via Tailscale, OpenAI, Claude, Gemini, Groq…

Cosa sa fare su Windows:
- "Hey Jarvis" per svegliarlo, Whisper per capirti, voce robot Piper
- Apre app (menu Start e app dello Store), siti, cartelle e file; installa programmi con **winget**; giochi Steam
- Finestre: affianca, massimizza, riduci, chiudi ("metti Chrome a sinistra e Word a destra")
- Guarda lo schermo con l'OCR integrato in Windows, usa mouse e tastiera (testo con accenti)
- Terminale **PowerShell** (i comandi distruttivi sono sempre bloccati), automode
- Volume, luminosità (portatili), musica, appunti, promemoria con notifica, Wi-Fi e Bluetooth, webcam
- Schermo sulla TV con Miracast (Win+K), immagini con Z-Image-Turbo (il modello si scarica al primo uso)
- Si aggiorna da solo: Personalizza → Aggiornamenti

Log in caso di problemi: `%LOCALAPPDATA%\NEXUS\nexus.log`
