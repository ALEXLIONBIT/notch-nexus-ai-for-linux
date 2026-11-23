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
