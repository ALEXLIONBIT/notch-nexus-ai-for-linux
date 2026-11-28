**Novità 0.7.0** — *Controlla aggiornamenti* guarda anche quello che sta attorno a NEXUS (Personalizza → Aggiornamenti → *Attorno a NEXUS*): la versione di **Ollama** (e se la nuova è già arrivata nei pacchetti del sistema), i **modelli** scaricati che su ollama.com hanno una versione nuova (si aggiornano con un tasto) e i **programmi del sistema** che NEXUS usa (screenshot, OCR, Tailscale, Qt…). Su Linux il tasto apre un terminale con l'aggiornamento del sistema (la password la scrivi tu), su Windows aggiorna Ollama e gli altri programmi con winget. Se un modello chiede un Ollama più nuovo, NEXUS te lo dice e ti porta lì.

**Novità 0.6.0** — Più compiti insieme: mentre NEXUS lavora puoi dire di nuovo "Ehi Nexus, …" e ti risponde subito, con l'altro compito che continua in background (schermo, mouse e browser li usa uno alla volta). Un compito per desktop virtuale (KDE, Mint e gli altri X11): le finestre restano sul desktop dove l'hai chiesto. "Ehi Nexus basta" (o "stop", "zitto") lo zittisce anche mentre parla e ferma il compito; nel notch c'è l'elenco dei compiti con la ✕. Ctrl+V nella chat incolla immagini e file, Ctrl+C e il pulsante copia copiano le risposte. Risolto "non ho lo strumento screenshot": se NEXUS partiva prima della sessione grafica non vedeva lo schermo.

**Novità 0.5.3** — Il notch non sparisce più dopo aver chiuso il coperchio, la sospensione o il cambio di monitor: quando lo schermo torna, NEXUS lo ricrea da solo.

**Novità 0.5.2** — Con Playwright attivo, *apri un sito* e *cerca* passano dal browser pilotato (prima aprivano il browser normale e Playwright restava inutilizzato): NEXUS legge la pagina e può continuare a cliccare e scrivere. Node.js viene trovato anche se installato con nvm.

**Novità 0.5.1** — Al primo avvio NEXUS scarica il riconoscimento vocale (Whisper, 1,6 GB): prima sembrava bloccato, ora nel notch compare l'avanzamento ("Scarico il riconoscimento vocale… 42% · 700 di 1600 MB"). I prossimi avvii sono immediati.

**Novità 0.5.0**
- **Personalità**: Personalizza → Ascolto → *Personalità*: scrivi come deve parlare (o tocca un esempio: Simpatico, Formale, Ironico, Coach, Pirata, Essenziale)
- **Usa il browser al posto tuo** (Playwright): apre i siti, legge le pagine, clicca e compila i moduli nel tuo browser predefinito (Chrome, Edge, Brave, Chromium… o Firefox). Serve Node.js. Login e pagamenti li fai tu
- **Ehi <nome> sistemato**: il saluto è obbligatorio ("robot" da solo o "il robot è rotto" non lo svegliano più) e capisce anche la pronuncia italiana "ehirobot". Nuovo: **La tua voce** → registra "Ehi <nome>" 3 volte e ti riconosce dal suono
- Trascrizione **Massima** (large-v3) per chi vuole meno parole sbagliate

**Novità 0.4.1** — *Ehi <nome>* non si attiva più da solo con rumori, silenzio o discorsi normali; aggiungendo un cervello con chiave API l'elenco dei modelli disponibili compare da solo (scrivi per cercare) e *Prova* ti suggerisce il nome giusto; in Aggiornamenti c'è il pulsante **Riavvia**.

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
