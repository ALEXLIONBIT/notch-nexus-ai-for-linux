"""Vedere con la webcam: scatta una foto e la mostra al cervello (modello con visione)."""
import glob
import subprocess

from . import tool, ToolResult
from ..config import CACHE
from ..osys import IS_WIN


def _capture_windows(out):
    """Windows: OpenCV con DirectShow/Media Foundation, prima webcam a colori che risponde."""
    import time
    import cv2
    for idx in range(3):
        for api in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            cap = cv2.VideoCapture(idx, api)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            frame, t0 = None, time.time()
            while time.time() - t0 < 1.8:                # l'esposizione automatica si sistema
                ok, f = cap.read()
                if ok:
                    frame = f
            cap.release()
            if frame is not None and frame.ndim == 3:
                h, w = frame.shape[:2]
                if w > 1024:
                    frame = cv2.resize(frame, (1024, int(h * 1024 / w)))
                cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                _brighten(out)
                return out
    raise RuntimeError("non riesco ad accedere alla webcam (è usata da un'altra app o la privacy di Windows la blocca?)")


def capture():
    out = CACHE / "camera.jpg"
    out.unlink(missing_ok=True)
    if IS_WIN:
        return _capture_windows(out)
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
