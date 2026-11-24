"""Tool: creare immagini con Z-Image-Turbo (in locale, sulla GPU del PC)."""
from . import tool, ToolResult
from .. import imagegen
from ..osys import open_path

SHAPES = {"quadrata": (1024, 1024), "verticale": (768, 1024), "orizzontale": (1024, 768)}


@tool("generate_image", "Crea un'immagine da una descrizione con Z-Image-Turbo (ci mette circa un minuto). "
      "Scrivi il prompt IN INGLESE e dettagliato: soggetto, stile, luce, inquadratura.",
      {"prompt": {"type": "string", "description": "descrizione dettagliata in inglese"},
       "shape": {"type": "string", "enum": list(SHAPES)}}, ["prompt"])
def generate_image(ctx, prompt, shape="quadrata"):
    w, h = SHAPES.get(shape, (1024, 1024))
    from ..osys import IS_WIN
    if IS_WIN and not imagegen.available():
        if not ctx.confirm("Per creare immagini devo scaricare il modello Z-Image-Turbo, circa 6 GB. Lo scarico?"):
            return "L'utente non vuole scaricare il modello di immagini."
        ctx.step("⬇️", "Scarico il modello di immagini (una volta sola)")
        if not imagegen.install(lambda t: ctx.step("⬇️", t)):
            return "Download del modello di immagini non riuscito."
    ctx.step("🎨", "Creo l'immagine (circa un minuto)")
    path = imagegen.generate(prompt, w, h)
    ctx.image(str(path))
    open_path(path)
    return ToolResult(f"Immagine creata e salvata in {path}. L'ho aperta sullo schermo.")
