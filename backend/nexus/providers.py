"""Provider del "cervello": Ollama (locale, in rete o via Tailscale) oppure API compatibili OpenAI
(OpenAI, OpenRouter, Groq, Gemini, Anthropic, LM Studio, vLLM, llama.cpp…).

Formato interno dei messaggi (neutro):
  {"role": "system"|"user"|"assistant"|"tool", "content": str,
   "images": [path]?,                                   # solo user
   "tool_calls": [{"id", "name", "arguments": dict}]?,  # solo assistant
   "tool_call_id": str?, "name": str?}                  # solo tool
"""
import base64
import json
import uuid

# preset mostrati nella UI quando aggiungi un provider
PRESETS = {
    "ollama":     {"label": "Ollama (questo PC, rete o Tailscale)", "kind": "ollama",
                   "base_url": "http://127.0.0.1:11434", "model": "qwen3.5:4b", "needs_key": False},
    "openai":     {"label": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1",
                   "model": "gpt-4.1-mini", "needs_key": True},
    "openrouter": {"label": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1",
                   "model": "qwen/qwen3-vl-30b-a3b-instruct", "needs_key": True},
    "groq":       {"label": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1",
                   "model": "meta-llama/llama-4-scout-17b-16e-instruct", "needs_key": True},
    "gemini":     {"label": "Google Gemini", "kind": "openai",
                   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                   "model": "gemini-2.5-flash", "needs_key": True},
    "anthropic":  {"label": "Anthropic (Claude)", "kind": "openai", "base_url": "https://api.anthropic.com/v1/",
                   "model": "claude-haiku-5-5", "needs_key": True},
    "lmstudio":   {"label": "LM Studio / server OpenAI in rete", "kind": "openai",
                   "base_url": "http://192.168.1.10:1234/v1", "model": "", "needs_key": False},
    "custom":     {"label": "Personalizzato (compatibile OpenAI)", "kind": "openai",
                   "base_url": "", "model": "", "needs_key": False},
}

DEFAULT_PROVIDER = {"id": "local", "name": "Ollama su questo PC", "preset": "ollama", "kind": "ollama",
                    "base_url": "http://127.0.0.1:11434", "api_key": "", "model": "qwen3.5:4b"}


class Cancelled(Exception):
    pass


def mask(key):
    return "" if not key else (key[:3] + "…" + key[-4:] if len(key) > 10 else "•••")


def public(p):
    """Provider senza la chiave in chiaro (da mandare alla UI)."""
    q = dict(p)
    q["api_key_hint"] = mask(p.get("api_key", ""))
    q.pop("api_key", None)
    return q


def _img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ---------------------------------------------------------------- Ollama

class OllamaProvider:
    def __init__(self, p, opts):
        import ollama
        self.ollama = ollama
        self.p, self.opts = p, opts
        self.client = ollama.Client(host=p["base_url"].rstrip("/"), timeout=120)

    def _convert(self, msgs):
        out = []
        for m in msgs:
            if m["role"] == "assistant":
                o = {"role": "assistant", "content": m.get("content", "")}
                if m.get("tool_calls"):
                    o["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["arguments"]}}
                                       for c in m["tool_calls"]]
                out.append(o)
            elif m["role"] == "tool":
                out.append({"role": "tool", "content": m["content"], "tool_name": m.get("name", "")})
            else:
                o = {"role": m["role"], "content": m.get("content", "")}
                if m.get("images"):
                    o["images"] = m["images"]
                out.append(o)
        return out

    def chat(self, msgs, tools, is_cancelled):
        opts = {"num_ctx": int(self.opts.get("num_ctx", 16384)), "temperature": 0.3}
        if self.opts.get("num_gpu") is not None:
            opts["num_gpu"] = int(self.opts["num_gpu"])
        kw = dict(model=self.p["model"], messages=self._convert(msgs), tools=tools, options=opts,
                  keep_alive="30m", stream=True)
        try:
            stream = self.client.chat(think=False, **kw)
        except (self.ollama.ResponseError, TypeError):
            stream = self.client.chat(**kw)
        content, calls = "", []
        for part in stream:
            if is_cancelled():
                raise Cancelled()
            content += part.message.content or ""
            for c in part.message.tool_calls or []:
                calls.append({"id": "call_" + uuid.uuid4().hex[:8], "name": c.function.name,
                              "arguments": dict(c.function.arguments or {})})
        return content, calls

    def list_models(self):
        return sorted(m.model for m in self.client.list().models)


# ---------------------------------------------------------------- OpenAI-compatibile

class OpenAIProvider:
    def __init__(self, p, opts):
        from openai import OpenAI
        self.p = p
        self.client = OpenAI(base_url=p["base_url"], api_key=p.get("api_key") or "nessuna-chiave", timeout=120)

    def _convert(self, msgs):
        out = []
        for m in msgs:
            if m["role"] == "assistant":
                o = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    o["tool_calls"] = [{"id": c["id"], "type": "function",
                                        "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                       for c in m["tool_calls"]]
                out.append(o)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""), "content": m["content"]})
            elif m.get("images"):
                parts = [{"type": "text", "text": m.get("content", "")}]
                for path in m["images"]:
                    parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_img_b64(path)}"}})
                out.append({"role": m["role"], "content": parts})
            else:
                out.append({"role": m["role"], "content": m.get("content", "")})
        return out

    def chat(self, msgs, tools, is_cancelled):
        stream = self.client.chat.completions.create(
            model=self.p["model"], messages=self._convert(msgs), tools=tools or None,
            temperature=0.3, stream=True)
        content, acc = "", {}
        try:
            for chunk in stream:
                if is_cancelled():
                    raise Cancelled()
                if not chunk.choices:
                    continue
                d = chunk.choices[0].delta
                content += d.content or ""
                for tc in d.tool_calls or []:
                    slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
        finally:
            stream.close()
        calls = []
        for i in sorted(acc):
            s = acc[i]
            try:
                args = json.loads(s["args"]) if s["args"].strip() else {}
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": s["id"] or "call_" + uuid.uuid4().hex[:8], "name": s["name"], "arguments": args})
        return content, calls

    def list_models(self):
        return sorted(m.id for m in self.client.models.list().data)

    def transcribe(self, wav_path, model):
        with open(wav_path, "rb") as f:
            r = self.client.audio.transcriptions.create(model=model, file=f, language="it")
        return r.text


def make(p, opts=None):
    return (OllamaProvider if p.get("kind") == "ollama" else OpenAIProvider)(p, opts or {})
