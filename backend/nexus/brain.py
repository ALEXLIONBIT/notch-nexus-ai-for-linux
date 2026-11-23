"""Il cervello: Qwen (vision + tool calling) via Ollama, con loop di azioni."""
import json
import re
import time
from datetime import datetime


SYSTEM = """Sei NEXUS, un assistente robot futuristico che vive dentro il computer {owner} \
(Linux, desktop KDE Plasma). Parli SEMPRE in italiano, in modo amichevole e diretto.
Le tue risposte vengono lette a voce: massimo 2 frasi brevi, niente elenchi, niente markdown, niente emoji.
NON chiudere con domande di cortesia ("vuoi altro?", "cosa vuoi guardare?"): fai una domanda SOLO se ti manca \
un'informazione indispensabile per finire il compito. Altrimenti termina con una frase affermativa.
Non dire MAI di aver fatto un'azione se non hai chiamato il tool: senza tool non succede niente sul PC.
Non rispondere MAI "non posso": trova sempre un modo con i tool. Esempi: per giocare o installare giochi usa
steam_game (installa o avvia un gioco Steam); per un programma usa find_app e se manca install_app;
se serve qualcosa che deve fare l'utente (login, password), apri tu la cosa giusta e diglielo in una frase.
Sii veloce: usa il tool più diretto. Preferisci SEMPRE il terminale (run_shell) e i tool diretti
(file, appunti, musica, luminosità, promemoria, read_webpage, Wi-Fi) invece di guardare lo schermo e cliccare.
Guarda lo schermo solo se la cosa si può fare unicamente con l'interfaccia grafica.
Hai dei tool per agire DAVVERO sul PC: usali invece di spiegare come fare.
- Per aprire programmi usa open_app, per siti open_url, per cercare web_search.
- Se ti serve sapere cosa c'è sullo schermo usa look_screen: ti dà l'immagine e i testi con la posizione [x,y].
- Puoi usare mouse e tastiera: click(x,y) con coordinate 0-1000, click_text per cliccare una scritta,
  type_text per scrivere, press_keys per le scorciatoie, scroll, drag, move_mouse.
- Per azioni sullo schermo segui sempre: look_screen → click/type → look_screen per controllare che abbia funzionato.
- Per scrivere in un'app: prima clicca nel campo giusto, poi type_text.
- Finestre: list_windows, place_window (sinistra/destra/quarti), split_screen per affiancarne due,
  window_action per attivare/massimizzare/ridurre/chiudere. Le app non aperte vengono aperte da sole.
- Immagini: generate_image con un prompt dettagliato IN INGLESE (soggetto, stile, luce, inquadratura).
- TV: list_tvs per vedere le TV, cast_screen per condividere lo schermo su una TV, stop_cast per fermare.
- organize_desktop e run_shell chiedono conferma da soli: non chiedere conferma tu prima.
Non inventare mai risultati: di' solo quello che i tool hanno restituito.
Data e ora attuali: {now}."""


ASKS_ACTION = re.compile(r"\b(apri|aprimi|avvia|lancia|cerca|scrivi|clicca|riordina|sistema|chiudi|vai su|"
                         r"metti|alza|abbassa|sposta|guarda|leggi|controlla|esegui)\b", re.I)
CLAIMS_ACTION = re.compile(r"\b(ecco|apro|aperto|sto aprendo|avviato|fatto|cercato|spostat|cliccat|scritto|"
                           r"alzato|abbassato|messo|chiuso)\b", re.I)


COURTESY = re.compile(r"(posso aiutarti|posso fare|serve altro|hai bisogno|desideri|preferisci|"
                      r"vuoi (che|altro|guardare|ascoltare|sapere|fare|provare)|cosa vuoi|altro\?|ti serve)", re.I)


def drop_courtesy(reply):
    """Toglie le domande di cortesia finali (Qwen le aggiunge anche se gli dici di no)."""
    parts = re.split(r"(?<=[.!?])\s+", reply.strip())
    while len(parts) > 1 and parts[-1].endswith("?") and COURTESY.search(parts[-1]):
        parts.pop()
    return " ".join(parts)


from .providers import Cancelled, make as make_provider  # noqa: E402


class Brain:
    def __init__(self, cfg, tools, ctx):
        self.cfg, self.tools, self.ctx = cfg, tools, ctx
        self.history = []
        self.last = 0.0
        self.cancelled = False

    def provider(self):
        """Il provider attivo (Ollama locale/remoto o API compatibile OpenAI)."""
        return make_provider(self.cfg.active_provider(), self.cfg)

    def _chat(self, messages):
        """Chiamata in streaming: si può interrompere a metà con stop."""
        return self.provider().chat(messages, self.tools.schemas, lambda: self.cancelled)

    def run(self, user_text):
        try:
            return self._run(user_text)
        except Exception as e:
            if "context" not in str(e).lower() or isinstance(e, Cancelled):
                raise
            self.history = []                       # contesto pieno: riparte con memoria pulita
            return self._run(user_text)

    @staticmethod
    def _only_last_image(msgs):
        """Tiene solo l'ultima immagine: le vecchie occupano migliaia di token."""
        seen = False
        for m in reversed(msgs):
            if m.get("images"):
                if seen:
                    m.pop("images")
                    m["content"] = "(screenshot precedente rimosso)"
                seen = True

    def _run(self, user_text):
        self.cancelled = False
        self.log_steps = []
        if time.time() - self.last > self.cfg["memory_minutes"] * 60:
            self.history = []
        self.last = time.time()
        now = datetime.now().strftime("%A %d %B %Y, %H:%M")
        msgs = [{"role": "system", "content": SYSTEM.format(
            now=now, owner=f"di {self.cfg['user_name']}" if self.cfg.get("user_name") else "dell'utente")}, *self.history,
                {"role": "user", "content": user_text}]
        reply = "Ho fatto troppi passaggi senza finire, riprova con una richiesta più semplice."
        used_tools, nudged = False, False
        seen_calls = {}
        finished = False
        for _ in range(self.cfg["max_steps"]):
            if self.cancelled:
                raise Cancelled()
            self._only_last_image(msgs)
            content, calls = self._chat(msgs)
            msgs.append({"role": "assistant", "content": content, **({"tool_calls": calls} if calls else {})})
            if not calls:
                reply = drop_courtesy(content) or "Fatto."
                # anti-bugia: ha detto di aver agito ma non ha chiamato nessun tool
                if not used_tools and not nudged and ASKS_ACTION.search(user_text) and CLAIMS_ACTION.search(reply):
                    nudged = True
                    msgs.pop()
                    msgs.append({"role": "system", "content": "Non hai chiamato nessun tool, quindi l'azione NON "
                                 "è stata fatta. Chiama adesso il tool giusto."})
                    continue
                finished = True
                break
            used_tools = True
            for c in calls:
                if self.cancelled:
                    raise Cancelled()
                name, args = c["name"], c["arguments"]
                key = name + json.dumps(args, sort_keys=True)
                seen_calls[key] = seen_calls.get(key, 0) + 1
                if seen_calls[key] > 1 and name not in ("look_screen", "press_keys", "scroll"):
                    # sta ripetendo la stessa azione: non rifarla, fallo concludere
                    msgs.append({"role": "tool", "content": "Hai GIÀ fatto questa azione con questo risultato. "
                                 "Non ripeterla: rispondi all'utente o prova un'altra strada.",
                                 "name": name, "tool_call_id": c["id"]})
                    continue
                res = self.tools.call(name, args)
                self.log_steps.append({"tool": name, "args": args, "result": res.text[:300]})
                msgs.append({"role": "tool", "content": res.text, "name": name, "tool_call_id": c["id"]})
                if res.image:
                    msgs.append({"role": "user", "content": "Ecco lo screenshot attuale dello schermo.",
                                 "images": [res.image]})
        if not finished:
            # limite di passaggi: invece di arrendersi, riassume cosa ha fatto e cosa manca
            try:
                msgs.append({"role": "system", "content": "Basta azioni. In una o due frasi di' all'utente cosa hai "
                             "fatto finora e cosa manca (o cosa deve fare lui)."})
                content, _ = self.provider().chat(msgs, [], lambda: self.cancelled)
                reply = drop_courtesy(content) or reply
            except Cancelled:
                raise
            except Exception:
                pass
        # memoria breve: niente immagini, risultati dei tool accorciati, ultimi 12 messaggi
        hist = []
        for mm in msgs[1:]:
            mm = {k: v for k, v in mm.items() if k != "images"}
            if mm["role"] == "tool" and len(mm["content"]) > 400:
                mm["content"] = mm["content"][:400] + "…"
            hist.append(mm)
        self.history = hist[-12:]
        while self.history and self.history[0]["role"] != "user":
            self.history.pop(0)
        return reply
