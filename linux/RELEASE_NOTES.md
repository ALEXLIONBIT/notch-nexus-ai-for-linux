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
Nell'AppImage il notch è una finestra normale (il layer-shell di KDE resta nell'installazione con `scripts/install.sh`).

Log in caso di problemi: `~/.local/share/nexus/nexus.log`
