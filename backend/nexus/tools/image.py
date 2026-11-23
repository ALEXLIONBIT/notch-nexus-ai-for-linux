"""Tool: creare immagini con Z-Image-Turbo (in locale, sulla GPU del PC)."""
import subprocess

from . import tool, ToolResult
from .. import imagegen

SHAPES = {"quadrata": (1024, 1024), "verticale": (768, 1024), "orizzontale": (1024, 768)}


@tool("generate_image", "Crea un'immagine da una descrizione con Z-Image-Turbo (ci mette circa un minuto). "
      "Scrivi il prompt IN INGLESE e dettagliato: soggetto, stile, luce, inquadratura.",
      {"prompt": {"type": "string", "description": "descrizione dettagliata in inglese"},
       "shape": {"type": "string", "enum": list(SHAPES)}}, ["prompt"])
def generate_image(ctx, prompt, shape="quadrata"):
    w, h = SHAPES.get(shape, (1024, 1024))
    ctx.step("🎨", "Creo l'immagine (circa un minuto)")
    path = imagegen.generate(prompt, w, h)
    ctx.image(str(path))
    subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return ToolResult(f"Immagine creata e salvata in {path}. L'ho aperta sullo schermo.")
