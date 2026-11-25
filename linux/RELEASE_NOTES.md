**Novità 0.5.0**
- **Personalità**: Personalizza → Ascolto → *Personalità*: scrivi come deve parlare (o tocca un esempio: Simpatico, Formale, Ironico, Coach, Pirata, Essenziale)
- **Usa il browser al posto tuo** (Playwright): apre i siti, legge le pagine, clicca e compila i moduli nel tuo browser predefinito (Chrome, Edge, Brave, Chromium… o Firefox). Serve Node.js. Login e pagamenti li fai tu
- **Ehi <nome> sistemato**: il saluto è obbligatorio ("robot" da solo o "il robot è rotto" non lo svegliano più) e capisce anche la pronuncia italiana "ehirobot". Nuovo: **La tua voce** → registra "Ehi <nome>" 3 volte e ti riconosce dal suono
- Trascrizione **Massima** (large-v3) per chi vuole meno parole sbagliate

**Novità 0.4.2** — Il primo avvio comincia dai **permessi**: mouse e tastiera (un clic su *Concedi* e la password, funziona subito senza uscire dalla sessione), microfono e lettura dello schermo, ognuno con il suo stato.

**Novità 0.4.1** — *Ehi <nome>* non si attiva più da solo con rumori, silenzio o discorsi normali; aggiungendo un cervello con chiave API l'elenco dei modelli disponibili compare da solo (scrivi per cercare) e *Prova* ti suggerisce il nome giusto; in Aggiornamenti c'è il pulsante **Riavvia**.

**Novità 0.4.0** — **Dagli il nome che vuoi**: Personalizza → Ascolto → *Come si chiama* (es. Marco) e scegli *Ehi Marco* come parola per svegliarlo. Puoi anche dire tutto di fila: “Marco, che tempo fa domani?”. Si presenta col suo nome. La prima volta scarica un piccolo modello (75 MB).

**Novità 0.3.0**
- **Chat**: pulsante 💬 nel notch → finestra con tutte le conversazioni salvate: cerca, riapri (NEXUS ricorda il discorso), nuova chat, elimina; scrivi o parla da lì
- **Modelli**: Personalizza → Modelli → cerca nel catalogo di Ollama, scarica con la barra di avanzamento, usa o elimina. Le taglie in azzurro entrano nella scheda video. Anche a voce: "installa qwen3 da 4b e usalo"

**NEXUS per Linux in un solo file (AppImage)**: lo stesso robot dell'installazione classica, senza script né Python da installare.

**Come si usa:** scarica `NEXUS-*-x86_64.AppImage`, rendilo eseguibile e aprilo:
```
chmod +x NEXUS-*-x86_64.AppImage
./NEXUS-*-x86_64.AppImage
```
Al primo avvio NEXUS si aggiunge al menu delle app e all'avvio automatico, e ti chiede dove deve ragionare:
- **Su questo PC**: installa Ollama (ti chiede la password) e scarica il cervello giusto per la tua scheda video
- **Con un provider**: il tuo PC di casa via Tailscale, OpenAI, Claude, Gemini, Groq…

**Mouse e tastiera virtuali**: li concedi al primo avvio; in alternativa, da terminale:
```
./NEXUS-*-x86_64.AppImage --permessi
```
poi esci e rientra.

Funziona su Ubuntu 22.04+, Linux Mint 21+, Debian 12+, Fedora, Arch/CachyOS (KDE, GNOME, Cinnamon…).
Per leggere lo schermo serve `tesseract` (pacchetto `tesseract-ocr`). Si aggiorna da solo: Personalizza → Aggiornamenti.

Log in caso di problemi: `~/.local/share/nexus/nexus.log`
