"""Info sul sistema e volume."""
import subprocess

import psutil

from . import tool
from ..osys import IS_WIN


@tool("system_info", "Stato del PC: batteria, CPU, RAM, disco.")
def system_info(ctx):
    ctx.step("📊", "Controllo il sistema")
    parts = [f"CPU {psutil.cpu_percent(interval=0.5):.0f}%",
             f"RAM {psutil.virtual_memory().percent:.0f}% usata",
             f"disco {psutil.disk_usage('C:/' if IS_WIN else '/').percent:.0f}% pieno"]
    b = psutil.sensors_battery()
    if b:
        parts.append(f"batteria {b.percent:.0f}% {'in carica' if b.power_plugged else 'scollegata'}")
    return ", ".join(parts)


@tool("set_volume", "Imposta il volume del PC in percentuale (0-100).",
      {"percent": {"type": "integer"}}, ["percent"])
def set_volume(ctx, percent):
    p = max(0, min(100, int(percent)))
    ctx.step("🔊", f"Volume {p}%")
    if IS_WIN:
        win_set_volume(p)
    else:
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{p / 100:.2f}"], timeout=5)
    return f"Volume al {p}%."


def win_set_volume(percent):
    """Volume principale di Windows (Core Audio via pycaw)."""
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()
    try:
        dev = AudioUtilities.GetSpeakers()
        vol = dev.EndpointVolume if hasattr(dev, "EndpointVolume") else None
        if vol is None:                                  # pycaw vecchio
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            vol = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
        vol.SetMute(0, None)
        vol.SetMasterVolumeLevelScalar(percent / 100, None)
    finally:
        comtypes.CoUninitialize()
