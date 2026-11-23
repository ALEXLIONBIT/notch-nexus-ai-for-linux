"""Comandi da terminale: chiede SEMPRE conferma, tranne pochi comandi di sola lettura."""
import subprocess
from pathlib import Path

from . import tool


@tool("run_shell", "Esegue un comando nel terminale Linux (bash). Usalo per cose che gli altri tool "
      "non fanno. Per comandi che modificano qualcosa l'utente deve confermare.",
      {"command": {"type": "string"}, "reason": {"type": "string", "description": "a cosa serve"}},
      ["command"])
def run_shell(ctx, command, reason=""):
    safe = any(command.strip().startswith(p) for p in ctx.cfg["safe_shell_prefixes"]) \
        and not any(c in command for c in (";", "&&", "|", ">", "`", "$("))
    ctx.step("💻", command[:80])
    if not safe and not ctx.confirm(f"Posso eseguire il comando: {command}?"):
        return "L'utente non ha dato il permesso."
    r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120,
                       cwd=Path.home())
    out = (r.stdout + r.stderr).strip()
    return f"exit {r.returncode}\n{out[-3000:] or '(nessun output)'}"
