"""Tool: i modelli AI di Ollama (cerca, installa, usa, elimina) — "installa qwen3 da 4b e usalo"."""
from . import tool
from .. import models


def _p(ctx):
    p = models.target(ctx.cfg)
    if p is None:
        raise RuntimeError("non c'è nessun Ollama tra i cervelli: aggiungine uno da Personalizza → Cervello")
    return p


def _emit_cfg(ctx):
    bus = getattr(getattr(ctx, "n", None), "bus", None)
    if bus:
        bus.emit("config", config=ctx.cfg.public())


@tool("ai_models",
      "Gestisce i modelli AI (il cervello) su Ollama: 'elenca' quelli installati, 'cerca' nel catalogo di ollama.com, "
      "'installa' (scarica), 'usa' (diventa il cervello attivo), 'elimina'. Nome nel formato ollama, es. qwen3:4b, gemma3:1b.",
      {"action": {"type": "string", "enum": ["elenca", "cerca", "installa", "usa", "elimina"]},
       "name": {"type": "string", "description": "modello (installa/usa/elimina) o testo da cercare (cerca)"},
       "use_after": {"type": "boolean", "description": "con 'installa': usalo subito dopo"}},
      ["action"])
def ai_models(ctx, action, name="", use_after=False):
    p = _p(ctx)
    name = (name or "").strip()
    if action == "elenca":
        ctx.step("🧠", "Modelli installati")
        cur = ctx.cfg.active_provider().get("model")
        ms = models.installed(p)
        return "; ".join(f"{m['name']} ({m['size_gb']} GB){' ← in uso' if m['name'] == cur else ''}" for m in ms) or "nessun modello"
    if action == "cerca":
        ctx.step("🔎", f"Cerco modelli: {name}")
        rs = models.search(name, 6)
        return "\n".join(f"{r['name']}: {', '.join(s['tag'] for s in r['sizes']) or 'una taglia'}"
                         f"{' [' + ', '.join(r['caps']) + ']' if r['caps'] else ''} — {r['desc'][:90]}" for r in rs) or "niente"
    if not name:
        raise RuntimeError("serve il nome del modello")
    if action == "installa":
        tag = name.split(":", 1)[1] if ":" in name else ""
        gb = models._size_gb(tag) if tag else None
        if not ctx.confirm(f"Scarico il modello {name}{f' (circa {gb} GB)' if gb else ''}?"):
            return "Annullato."
        models.pull(p, name, lambda t, pct: ctx.step("⬇️", t) if pct % 10 == 0 or pct < 0 else None)
        if use_after:
            return ai_models(ctx, "usa", name)
        return f"Modello {name} installato."
    if action == "usa":
        have = [m["name"] for m in models.installed(p)]
        if name not in have and name.split(":")[0] not in have:
            raise RuntimeError(f"{name} non è installato (installati: {', '.join(have[:8])})")
        p["model"] = name
        ctx.cfg["provider"] = p["id"]
        ctx.cfg.save()
        _emit_cfg(ctx)
        ctx.step("🧠", f"Cervello: {name}")
        return f"Da adesso uso {name}."
    if action == "elimina":
        if not ctx.confirm(f"Elimino il modello {name}?"):
            return "Annullato."
        models.delete(p, name)
        return f"Modello {name} eliminato."
    raise RuntimeError("azione sconosciuta")
