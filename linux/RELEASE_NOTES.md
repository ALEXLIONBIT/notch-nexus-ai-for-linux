**Novità 0.3.1** — su KDE Plasma (Wayland) il notch torna come deve essere: in alto al centro, sopra le finestre, senza voce nella barra delle applicazioni. L'AppImage usa il layer-shell di KDE già presente nel sistema (servono i pacchetti `pyside6` e `layer-shell-qt`, già installati su Plasma; su Ubuntu: `python3-pyside6.qtquick`). Senza, il notch passa da XWayland e resta comunque in alto e fuori dalla barra.

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

**Mouse e tastiera virtuali** (per cliccare e scrivere al posto tuo), una volta sola:
```
./NEXUS-*-x86_64.AppImage --permessi
```
poi esci e rientra.

Funziona su Ubuntu 22.04+, Linux Mint 21+, Debian 12+, Fedora, Arch/CachyOS (KDE, GNOME, Cinnamon…).
Per leggere lo schermo serve `tesseract` (pacchetto `tesseract-ocr`). Si aggiorna da solo: Personalizza → Aggiornamenti.

Log in caso di problemi: `~/.local/share/nexus/nexus.log`
