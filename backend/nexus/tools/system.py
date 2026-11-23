"""Info sul sistema e volume."""
import subprocess

import psutil

from . import tool


@tool("system_info", "Stato del PC: batteria, CPU, RAM, disco.")
def system_info(ctx):
    ctx.step("📊", "Controllo il sistema")
    parts = [f"CPU {psutil.cpu_percent(interval=0.5):.0f}%",
             f"RAM {psutil.virtual_memory().percent:.0f}% usata",
             f"disco {psutil.disk_usage('/').percent:.0f}% pieno"]
    b = psutil.sensors_battery()
    if b:
        parts.append(f"batteria {b.percent:.0f}% {'in carica' if b.power_plugged else 'scollegata'}")
    return ", ".join(parts)


@tool("set_volume", "Imposta il volume del PC in percentuale (0-100).",
      {"percent": {"type": "integer"}}, ["percent"])
def set_volume(ctx, percent):
    p = max(0, min(100, int(percent)))
    ctx.step("🔊", f"Volume {p}%")
    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{p / 100:.2f}"], timeout=5)
    return f"Volume al {p}%."
