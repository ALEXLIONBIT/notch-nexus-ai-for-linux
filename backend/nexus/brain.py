"""Il cervello: Qwen (vision + tool calling) via Ollama, con loop di azioni."""
import json
import re
import threading
import time
from datetime import datetime


SYSTEM = """Ti chiami {name}: sei un assistente robot futuristico che vive dentro il computer {owner} \
({os}). Parli SEMPRE in italiano, in modo amichevole e diretto.
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
- Webcam: look_camera quando l'utente dice "guarda la telecamera", "cosa vedi?", "cosa ho in mano?".
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



def personality_text(p):
    """La personalità scritta dall'utente (Personalizza → Personalità): cambia il modo di parlare, non le regole."""
    p = (p or "").strip()[:1200]
    if not p:
        return ""
    return ("\n\nPERSONALITÀ scelta dall'utente (segui questo stile in ogni risposta, ma resta sempre utile, onesto, "
            "in italiano, breve perché le risposte sono lette a voce, e non smettere mai di usare i tool quando servono):\n" + p)

class Brain:
    """Il cervello è uno solo ma lavora a più compiti insieme: ogni compito (tasks.Task) ha il suo stop
    e la memoria breve del suo desktop (lane: {"history": [...], "last": tempo})."""

    def __init__(self, cfg, tools, ctx):
        self.cfg, self.tools, self.ctx = cfg, tools, ctx
        self.lock = threading.Lock()

    def provider(self):
        """Il provider attivo (Ollama locale/remoto o API compatibile OpenAI)."""
        return make_provider(self.cfg.active_provider(), self.cfg)

    def _chat(self, messages, task):
        """Chiamata in streaming: si può interrompere a metà con stop.
        Se il cervello scelto non risponde, propone di passare a quello locale e riprova."""
        ctx = task.ctx or self.ctx
        try:
            return self.provider().chat(messages, self.tools.schemas, lambda: task.cancelled)
        except Cancelled:
            raise
        except Exception as e:
            if "context" in str(e).lower():
                raise
            fb = self._fallback()
            if not fb:
                raise
            cur = self.cfg.active_provider()
            print(f"cervello '{cur.get('name')}' non risponde: {str(e)[:150]}")
            if not ctx.confirm(f"Il cervello {cur.get('name')} non risponde. Passo a quello locale, {fb.get('model')} su questo PC?"):
                raise
            self.cfg["provider"] = fb["id"]
            self.cfg.save()
            ctx.n.bus.emit("config", config=self.cfg.public())
            ctx.step("🔁", f"Uso il cervello locale ({fb.get('model')})")
            return self.provider().chat(messages, self.tools.schemas, lambda: task.cancelled)

    def _fallback(self):
        """Un cervello Ollama su questo PC, diverso da quello attivo."""
        cur = self.cfg.active_provider()
        for p in self.cfg["providers"]:
            local = any(h in p.get("base_url", "") for h in ("127.0.0.1", "localhost"))
            if p["id"] != cur["id"] and p.get("kind") == "ollama" and local:
                return p
        return None

    def run(self, user_text, task, lane, images=None, others=""):
        try:
            return self._run(user_text, task, lane, images, others)
        except Exception as e:
            if "context" not in str(e).lower() or isinstance(e, Cancelled):
                raise
            with self.lock:
                lane["history"] = []                 # contesto pieno: riparte con memoria pulita
            return self._run(user_text, task, lane, images, others)

    @staticmethod
    def _only_last_image(msgs):
        """Tiene solo l'ultima immagine: le vecchie occupano migliaia di token."""
        seen = False
        for m in reversed(msgs):
            if m.get("images"):
                if seen:
                    m.pop("images")
                    if m.get("auto"):
                        m["content"] = "(screenshot precedente rimosso)"
                    else:                            # immagine incollata dall'utente: il testo della richiesta resta
                        m["content"] = (m.get("content") or "") + " (immagine allegata già vista)"
                seen = True

    def _run(self, user_text, task, lane, images, others):
        if task.cancelled:
            raise Cancelled()
        task.log_steps = []
        ctx = task.ctx or self.ctx
        with self.lock:
            if time.time() - lane.get("last", 0) > self.cfg["memory_minutes"] * 60:
                lane["history"] = []
            lane["last"] = time.time()
            past = list(lane.get("history") or [])
        now = datetime.now().strftime("%A %d %B %Y, %H:%M")
        from .osys import os_name
        system = SYSTEM.format(
            now=now, os=os_name(), name=(self.cfg.get("agent_name") or "Nexus").strip(),
            owner=f"di {self.cfg['user_name']}" if self.cfg.get("user_name") else "dell'utente")
        system += personality_text(self.cfg.get("personality", ""))
        from .tools import REGISTRY
        if "browser_navigate" in REGISTRY:
            from .browsermcp import GUIDE
            system += GUIDE
        system += others
        user = {"role": "user", "content": user_text}
        if images:
            user["images"] = list(images)
        msgs = [{"role": "system", "content": system}, *past, user]
        reply = "Ho fatto troppi passaggi senza finire, riprova con una richiesta più semplice."
        used_tools, nudged = False, False
        seen_calls = {}
        finished = False
        for _ in range(self.cfg["max_steps"]):
            if task.cancelled:
                raise Cancelled()
            self._only_last_image(msgs)
            content, calls = self._chat(msgs, task)
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
                if task.cancelled:
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
                gate = getattr(ctx, "before_tool", None)
                note = gate(name, args or {}) if gate else ""     # mani occupate da un altro compito: aspetta
                if task.cancelled:
                    raise Cancelled()
                if note.startswith("SKIP:"):                       # lo schermo è cambiato mentre aspettava
                    msgs.append({"role": "tool", "content": note[5:], "name": name, "tool_call_id": c["id"]})
                    continue
                res = self.tools.call(name, args, ctx)
                self.log_steps_add(task, name, args, res.text)
                msgs.append({"role": "tool", "content": res.text, "name": name, "tool_call_id": c["id"]})
                if res.image:
                    msgs.append({"role": "user", "content": "Ecco lo screenshot attuale dello schermo.",
                                 "images": [res.image], "auto": True})
        if not finished:
            # limite di passaggi: invece di arrendersi, riassume cosa ha fatto e cosa manca
            try:
                msgs.append({"role": "system", "content": "Basta azioni. In una o due frasi di' all'utente cosa hai "
                             "fatto finora e cosa manca (o cosa deve fare lui)."})
                content, _ = self.provider().chat(msgs, [], lambda: task.cancelled)
                reply = drop_courtesy(content) or reply
            except Cancelled:
                raise
            except Exception:
                pass
        # memoria breve del desktop: niente immagini, risultati dei tool accorciati, ultimi 12 messaggi.
        # Si aggiunge in coda (un altro compito dello stesso desktop può aver finito nel frattempo).
        new = []
        for mm in msgs[1 + len(past):]:
            if mm["role"] == "system":
                continue
            mm = {k: v for k, v in mm.items() if k not in ("images", "auto")}
            if mm["role"] == "tool" and len(mm["content"]) > 400:
                mm["content"] = mm["content"][:400] + "…"
            new.append(mm)
        if not finished:
            new.append({"role": "assistant", "content": reply})
        with self.lock:
            hist = (list(lane.get("history") or []) + new)[-12:]
            while hist and hist[0]["role"] != "user":
                hist.pop(0)
            lane["history"] = hist
            lane["last"] = time.time()
        return reply

    @staticmethod
    def log_steps_add(task, name, args, text):
        task.log_steps.append({"tool": name, "args": args, "result": text[:300]})
