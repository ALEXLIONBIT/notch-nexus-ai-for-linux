"""Vedere con la webcam: scatta una foto e la mostra al cervello (modello con visione)."""
import glob
import subprocess

from . import tool, ToolResult
from ..config import CACHE


def capture():
    out = CACHE / "camera.jpg"
    out.unlink(missing_ok=True)
    devices = sorted(glob.glob("/dev/video*")) or ["/dev/video0"]
    for dev in devices:                                  # la prima a colori che funziona
        fmts = subprocess.run(["v4l2-ctl", "-d", dev, "--list-formats"], capture_output=True, text=True).stdout
        if "GREY" in fmts and "YUYV" not in fmts and "MJPG" not in fmts:
            continue                                     # telecamera a infrarossi (Windows Hello)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2", "-video_size", "1280x720",
                            "-i", dev, "-ss", "1.8", "-frames:v", "1", "-vf", "scale=1024:-2", "-y", str(out)],
                           capture_output=True, timeout=25)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            _brighten(out)
            return out
    raise RuntimeError("non riesco ad accedere alla webcam (è usata da un'altra app?)")


def _brighten(path):
    """Se la stanza è buia, alza la luminosità (così il modello vede qualcosa)."""
    from PIL import Image, ImageOps, ImageStat
    im = Image.open(path).convert("RGB")
    if ImageStat.Stat(im.convert("L")).mean[0] < 45:
        ImageOps.autocontrast(im, cutoff=1).save(path, quality=88)


@tool("look_camera", "Guarda con la webcam del PC (scatta una foto e te la mostra). Usalo quando l'utente dice "
      "'guarda la telecamera', 'cosa vedi?', 'come sto?', 'cosa ho in mano?'.",
      {"question": {"type": "string", "description": "cosa guardare"}})
def look_camera(ctx, question=""):
    ctx.step("📷", "Guardo con la webcam")
    path = capture()
    ctx.image(str(path))
    return ToolResult("Ecco la foto appena scattata dalla webcam (immagine allegata). Descrivi cosa vedi.", image=str(path))
