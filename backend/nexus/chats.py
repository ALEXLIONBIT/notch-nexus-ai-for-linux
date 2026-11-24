"""Chat salvate: ogni conversazione è un file JSON in ~/.local/share/nexus/chats/ (o %LOCALAPPDATA%\\NEXUS\\chats).

{"id", "title", "created", "updated", "messages": [{"role": "user"|"assistant", "text", "time"}],
 "history": [...]}   ← la memoria del cervello, così riaprendo la chat si riprende il discorso
"""
import json
import threading
import time
import uuid

from .config import DATA

DIR = DATA / "chats"
_lock = threading.Lock()


def _path(cid):
    return DIR / f"{cid}.json"


def _title(text):
    t = " ".join(text.split())
    return (t[:48] + "…") if len(t) > 48 else (t or "Chat")


def new():
    now = time.time()
    return {"id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4], "title": "", "created": now, "updated": now,
            "messages": [], "history": []}


def save(chat):
    DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = _path(chat["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_path(chat["id"]))


def load(cid):
    try:
        return json.loads(_path(cid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def add(chat, role, text):
    chat["messages"].append({"role": role, "text": text, "time": time.time()})
    chat["updated"] = time.time()
    if not chat["title"] and role == "user":
        chat["title"] = _title(text)
    save(chat)


def delete(cid):
    _path(cid).unlink(missing_ok=True)


def rename(cid, title):
    c = load(cid)
    if c:
        c["title"] = title.strip()[:80] or c["title"]
        save(c)


def listing(query="", limit=200):
    """Elenco (più recenti prima); con query cerca nel titolo e nei messaggi."""
    q = query.strip().lower()
    out = []
    if not DIR.exists():
        return out
    for f in DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not c.get("messages"):
            continue
        hit = ""
        if q:
            if q in c.get("title", "").lower():
                hit = c["title"]
            else:
                for m in c["messages"]:
                    i = m["text"].lower().find(q)
                    if i >= 0:
                        s = max(0, i - 30)
                        hit = ("…" if s else "") + m["text"][s:i + 60].replace("\n", " ") + "…"
                        break
            if not hit:
                continue
        last = c["messages"][-1]["text"].replace("\n", " ")
        out.append({"id": c["id"], "title": c.get("title") or "Chat", "updated": c["updated"],
                    "count": len(c["messages"]), "preview": hit or last[:90]})
    out.sort(key=lambda c: c["updated"], reverse=True)
    return out[:limit]
