"""Il cervello: Qwen (vision + tool calling) via Ollama, con loop di azioni."""
import re
import time
from datetime import datetime

import ollama

SYSTEM = """Sei NEXUS, un assistente robot futuristico che vive dentro il computer {owner} \
(Linux, desktop KDE Plasma). Parli SEMPRE in italiano, in modo amichevole e diretto.
Le tue risposte vengono lette a voce: massimo 2 frasi brevi, niente elenchi, niente markdown, niente emoji.
NON chiudere con domande di cortesia ("vuoi altro?", "cosa vuoi guardare?"): fai una domanda SOLO se ti manca \
un'informazione indispensabile per finire il compito. Altrimenti termina con una frase affermativa.
Non dire MAI di aver fatto un'azione se non hai chiamato il tool: senza tool non succede niente sul PC.
Hai dei tool per agire DAVVERO sul PC: usali invece di spiegare come fare.
- Per aprire programmi usa open_app, per siti open_url, per cercare web_search.
- Se ti serve sapere cosa c'è sullo schermo usa look_screen: ti dà l'immagine e i testi con la posizione [x,y].
- Puoi usare mouse e tastiera: click(x,y) con coordinate 0-1000, click_text per cliccare una scritta,
  type_text per scrivere, press_keys per le scorciatoie, scroll, drag, move_mouse.
- Per azioni sullo schermo segui sempre: look_screen → click/type → look_screen per controllare che abbia funzionato.
- Per scrivere in un'app: prima clicca nel campo giusto, poi type_text.
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


class Cancelled(Exception):
    pass


class Brain:
    def __init__(self, cfg, tools, ctx):
        self.cfg, self.tools, self.ctx = cfg, tools, ctx
        self.client = ollama.Client(host=cfg["ollama_host"])
        self.history = []
        self.last = 0.0
        self.cancelled = False

    def _chat(self, messages):
        """Chiamata in streaming: si può interrompere a metà con stop."""
        opts = {"num_ctx": int(self.cfg.get("num_ctx", 16384)), "temperature": 0.3}
        if self.cfg.get("num_gpu") is not None:
            opts["num_gpu"] = int(self.cfg["num_gpu"])
        kw = dict(model=self.cfg["model"], messages=messages, tools=self.tools.schemas,
                  options=opts, keep_alive="30m", stream=True)
        try:
            stream = self.client.chat(think=False, **kw)
        except (ollama.ResponseError, TypeError):
            stream = self.client.chat(**kw)
        content, calls = "", []
        for part in stream:
            if self.cancelled:
                stream.close() if hasattr(stream, "close") else None
                raise Cancelled()
            content += part.message.content or ""
            calls.extend(part.message.tool_calls or [])
        return content, calls

    def run(self, user_text):
        try:
            return self._run(user_text)
        except ollama.ResponseError as e:
            if "context" not in str(e).lower():
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
        if time.time() - self.last > self.cfg["memory_minutes"] * 60:
            self.history = []
        self.last = time.time()
        now = datetime.now().strftime("%A %d %B %Y, %H:%M")
        msgs = [{"role": "system", "content": SYSTEM.format(
            now=now, owner=f"di {self.cfg['user_name']}" if self.cfg.get("user_name") else "dell'utente")}, *self.history,
                {"role": "user", "content": user_text}]
        reply = "Ho fatto troppi passaggi senza finire, riprova con una richiesta più semplice."
        used_tools, nudged = False, False
        for _ in range(self.cfg["max_steps"]):
            if self.cancelled:
                raise Cancelled()
            self._only_last_image(msgs)
            content, calls = self._chat(msgs)
            msgs.append({"role": "assistant", "content": content,
                         **({"tool_calls": [c.model_dump() for c in calls]} if calls else {})})
            if not calls:
                reply = drop_courtesy(content) or "Fatto."
                # anti-bugia: ha detto di aver agito ma non ha chiamato nessun tool
                if not used_tools and not nudged and ASKS_ACTION.search(user_text) and CLAIMS_ACTION.search(reply):
                    nudged = True
                    msgs.pop()
                    msgs.append({"role": "system", "content": "Non hai chiamato nessun tool, quindi l'azione NON "
                                 "è stata fatta. Chiama adesso il tool giusto."})
                    continue
                break
            used_tools = True
            for c in calls:
                if self.cancelled:
                    raise Cancelled()
                name, args = c.function.name, dict(c.function.arguments or {})
                res = self.tools.call(name, args)
                msgs.append({"role": "tool", "content": res.text, "tool_name": name})
                if res.image:
                    msgs.append({"role": "user", "content": "Ecco lo screenshot attuale dello schermo.",
                                 "images": [res.image]})
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
