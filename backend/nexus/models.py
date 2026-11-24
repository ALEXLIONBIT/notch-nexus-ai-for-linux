"""Modelli di Ollama: cerca nel catalogo di ollama.com, scarica, usa ed elimina.

Lavora sull'Ollama del cervello attivo (questo PC, un PC in casa o via Tailscale); se il cervello attivo
non è Ollama, sul primo Ollama configurato.
"""
import html
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (nexus-assistant)"}


def target(cfg):
    """Il provider Ollama su cui installare: quello attivo, altrimenti il primo Ollama configurato."""
    p = cfg.active_provider()
    if p.get("kind") == "ollama":
        return p
    return next((q for q in cfg["providers"] if q.get("kind") == "ollama"), None)


def _req(p, path, data=None, method=None, timeout=20):
    url = p["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if p.get("api_key"):
        headers["Authorization"] = "Bearer " + p["api_key"]
    body = json.dumps(data).encode() if data is not None else None
    return urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=timeout)


def _gb(n):
    return round(n / 1e9, 1)


def installed(p):
    with _req(p, "/api/tags") as r:
        data = json.loads(r.read())
    out = []
    for m in data.get("models", []):
        d = m.get("details") or {}
        out.append({"name": m["name"].removesuffix(":latest"), "size_gb": _gb(m.get("size", 0)),
                    "params": d.get("parameter_size", ""), "quant": d.get("quantization_level", ""),
                    "family": d.get("family", "")})
    return sorted(out, key=lambda m: m["name"])


def _size_gb(tag):
    """Stima del download per una taglia tipo '4b', '0.5b', '270m', 'e2b' (pesi a 4 bit)."""
    m = re.search(r"([\d.]+)\s*([bm])", tag.lower())
    if not m:
        return None
    n = float(m.group(1)) * (1 if m.group(2) == "b" else 0.001)
    return round(n * 0.62 + 0.15, 1)


def search(q, limit=12):
    """Cerca su ollama.com. Ritorna [{name, desc, caps, sizes:[{tag, gb}], downloads}]."""
    url = "https://ollama.com/search?q=" + urllib.parse.quote(q or "")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        page = r.read().decode("utf-8", "replace")
    out = []
    for block in re.split(r'<a href="/library/', page)[1:]:
        name = block.split('"', 1)[0]
        if "/" in name or not name:
            continue
        desc = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        caps = re.findall(r'bg-indigo-50[^>]*>([^<]+)<', block)
        sizes = re.findall(r'bg-\[#ddf4ff\][^>]*>([^<]+)<', block)
        dl = re.search(r'title="([\d,]+) downloads"', block)
        out.append({"name": name, "desc": html.unescape(re.sub(r"<[^>]+>", "", desc.group(1))).strip() if desc else "",
                    "caps": [c.strip() for c in caps], "downloads": int(dl.group(1).replace(",", "")) if dl else 0,
                    "sizes": [{"tag": s.strip(), "gb": _size_gb(s)} for s in sizes]})
        if len(out) >= limit:
            break
    return out


def pull(p, name, progress):
    """Scarica un modello; progress(testo, percentuale) durante il download."""
    last = -1
    with _req(p, "/api/pull", {"model": name, "stream": True}, timeout=3600) as r:
        for line in r:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("error"):
                raise RuntimeError(ev["error"])
            total, done = ev.get("total") or 0, ev.get("completed") or 0
            if total:
                pct = int(done * 100 / total)
                if pct != last:
                    last = pct
                    progress(f"Scarico {name}… {pct}% di {_gb(total)} GB", pct)
            elif ev.get("status"):
                progress(f"{name}: {ev['status']}", last)


def delete(p, name):
    _req(p, "/api/delete", {"model": name}, method="DELETE").close()


def fits(gb, vram_mb):
    """Consiglio per la UI: entra nella scheda video, va (lento) col processore e la RAM, troppo grande."""
    if gb is None:
        return ""
    if vram_mb and gb * 1.2 * 1024 <= vram_mb:
        return "gpu"
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / 2**30
    except Exception:
        ram_gb = 8
    return "cpu" if gb * 1.3 <= ram_gb * 0.7 else "big"
