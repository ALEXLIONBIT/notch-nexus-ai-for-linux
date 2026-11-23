"""Registro dei tool che il cervello può usare."""
import traceback
from dataclasses import dataclass

REGISTRY = {}


@dataclass
class ToolResult:
    text: str
    image: str | None = None   # percorso di un'immagine da mostrare al modello


def tool(name, description, params=None, required=()):
    def deco(fn):
        REGISTRY[name] = (fn, {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": params or {},
                               "required": list(required)},
            },
        })
        return fn
    return deco


class Tools:
    def __init__(self, ctx):
        self.ctx = ctx
        from . import apps, desktop, screen, inputs, shell, system, windows, cast, install, image, extra, camera  # noqa: F401  (registrano i tool)

    @property
    def schemas(self):
        return [s for _, s in REGISTRY.values()]

    def call(self, name, args):
        if name not in REGISTRY:
            return ToolResult(f"Tool sconosciuto: {name}")
        fn, _ = REGISTRY[name]
        try:
            res = fn(self.ctx, **(args or {}))
            return res if isinstance(res, ToolResult) else ToolResult(str(res))
        except TypeError as e:
            return ToolResult(f"Argomenti sbagliati per {name}: {e}")
        except Exception as e:
            traceback.print_exc()
            return ToolResult(f"Errore in {name}: {e}")
