# NEXUS: Notch AI for Linux

Un assistente robot **sempre acceso** che vive dentro il tuo PC Linux. Lo svegli con la voce, ti risponde parlando e
**agisce davvero**: apre app e siti, riordina il desktop, guarda lo schermo, usa mouse e tastiera.
Tutto **in locale**, senza abbonamenti e senza limiti.

In alto c'è un **notch come quello del Mac** che mostra cosa sta facendo, con i sottotitoli in diretta.
Con un clic diventa un **casco robot a schermo intero** con il volto a LED, completamente personalizzabile.

![Personalizza](docs/screenshots/personalizza.jpg)

| Natale | Halloween | KDE Plasma |
|---|---|---|
| ![Natale](docs/screenshots/tema-natale.jpg) | ![Halloween](docs/screenshots/tema-halloween.jpg) | ![KDE Plasma](docs/screenshots/tema-plasma.jpg) |

## Cosa sa fare

- **Parola di attivazione** ("Hey Jarvis", "Alexa"…) con openWakeWord, oppure pulsante o scorciatoia (`nexus-ctl listen`)
- **Capisce l'italiano** con Whisper large-v3-turbo e capisce da solo quando hai finito di parlare (Silero VAD)
- **Cervello locale**: Qwen 3.5 con visione e tool, tramite Ollama (4B entra tutto in una GPU da 6 GB)
- **Vede lo schermo**: screenshot e OCR con le posizioni dei testi, così sa dove cliccare
- **Mouse e tastiera su Wayland**: dispositivi virtuali uinput con coordinate assolute, precisi a ogni scala
- **Azioni**: apre app, siti e cartelle, cerca sul web, riordina il desktop (con conferma e annulla), comandi da
  terminale (sempre con conferma), volume, batteria
- **Voce robotica** in italiano (Piper e un filtro robot regolabile) e sottotitoli karaoke sincronizzati
- **Stop vero**: ferma subito voce, ascolto e ragionamento

## Personalizzazione

- **Temi**: Perla, Grafite, OLED, Natale (neve e cappello), Halloween (zucca e pipistrelli), KDE Plasma
- **Colori liberi**: principale, secondario, guscio, sfondo
- **Faccia**: occhi tondi, quadrati, linee, triangoli, cuori; bocche diverse; LED tondi o a pixel; bagliore
- **Corpo**: casco a capsula, tondo, TV o cubo; antenne; orecchie
- **Disegna il tuo robot**: editor a LED con 9 colori. I tuoi occhi e la tua bocca continuano a sbattere le
  palpebre e a parlare

![Editor](docs/screenshots/editor.jpg)

## Requisiti

- Linux con **KDE Plasma su Wayland** (testato su CachyOS); su altri desktop il notch usa finestre normali
- GPU NVIDIA consigliata (testato su RTX 3060 6 GB); funziona anche solo su CPU, più lento
- Microfono e casse

## Installazione

```bash
# 1. pacchetti di sistema (Arch / CachyOS)
sudo pacman -S --needed ollama-cuda sox uv layer-shell-qt pyside6 wl-clipboard \
     tesseract tesseract-data-ita tesseract-data-eng spectacle
sudo systemctl enable --now ollama

# 2. NEXUS
git clone https://github.com/ALEXLIONBIT/notch-nexus-ai-for-linux.git ~/nexus
cd ~/nexus && ./scripts/install.sh

# 3. avvio automatico
systemctl --user enable --now nexus-backend nexus-ui
```

Le impostazioni personali vanno in `config.json`, creato al primo salvataggio dalla UI. Per esempio
`"user_name": "Mario"` fa sì che il robot ti chiami per nome, e `"model": "qwen3.5:9b"` cambia cervello.

> ⚠️ Con GPU da 6 GB carica **un solo modello** per volta: più modelli CUDA insieme possono bloccare il driver NVIDIA.

## Come è fatto

```
mic → wake word → Whisper → Qwen (Ollama, tool calling) → azioni (app, file, schermo, mouse/tastiera)
                                    ↓
                         Piper (voce robot) + eventi → UI (notch + casco, PySide6/QML + layer-shell)
```

- `backend/nexus/`: voce, cervello, tool (Python 3.11)
- `ui/`: notch e casco robot (QML), temi ed editor
- Backend e UI comunicano con JSON su `127.0.0.1:8765`

## English

NEXUS is an always-on, voice-driven AI assistant for Linux (KDE Plasma / Wayland). It shows a macOS-style
notch with live subtitles and a fully customizable LED-face robot helmet. Everything runs locally: openWakeWord,
faster-whisper, Qwen 3.5 via Ollama (vision and tool calling) and Piper TTS. It can open apps, read the screen with
OCR, and control the mouse and keyboard through uinput. The UI is in Italian for now.

## Licenze

- Codice: MIT (vedi `LICENSE`)
- Font Doto e Manrope: SIL Open Font License 1.1 (`ui/fonts/OFL-*.txt`)
- Modelli scaricati a parte con le loro licenze: Qwen (Apache 2.0), Whisper (MIT), Piper voices, openWakeWord
