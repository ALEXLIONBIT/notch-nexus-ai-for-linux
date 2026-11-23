"""Terminale: comandi bash veri. In modalità Manuale chiede conferma, in Auto no.
Alcuni comandi distruttivi sono SEMPRE bloccati."""
import os
import re
import subprocess
from pathlib import Path

from . import tool

_cwd = {"dir": str(Path.home())}

# mai, nemmeno in automode
DENY = [r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME)\s*($|;|&)", r"\bmkfs", r"\bdd\s+.*of=/dev/", r":\(\)\s*\{",
        r">\s*/dev/(sd|nvme)", r"\bwipefs\b", r"\bchmod\s+-R\s+0?777\s+/\s*$", r"\bshred\s+/dev/"]


@tool("run_shell", "Esegue comandi nel terminale Linux (bash) e ritorna l'output. Usalo spesso: è il modo più "
      "veloce per fare quasi tutto (file, programmi, info di sistema, git, script, installazioni flatpak, ecc). "
      "La cartella corrente resta tra un comando e l'altro. Niente comandi interattivi; sudo non è disponibile.",
      {"command": {"type": "string"}, "reason": {"type": "string", "description": "a cosa serve, in breve"}},
      ["command"])
def run_shell(ctx, command, reason=""):
    if any(re.search(p, command) for p in DENY):
        return "Comando bloccato: è troppo pericoloso (potrebbe cancellare il sistema o un disco)."
    safe = any(command.strip().startswith(p) for p in ctx.cfg["safe_shell_prefixes"]) \
        and not any(c in command for c in (";", "&&", "|", ">", "`", "$("))
    ctx.step("💻", command[:80])
    if not safe and not ctx.confirm(f"Posso eseguire il comando: {command}?"):
        return "L'utente non ha dato il permesso."
    # "cd cartella" cambia la cartella per i comandi successivi
    wrapped = f"cd {_q(_cwd['dir'])} && {command}\necho __NEXUS_PWD__=$PWD"
    try:
        r = subprocess.run(["bash", "-lc", wrapped], capture_output=True, text=True, timeout=300,
                           env=dict(os.environ, TERM="dumb", PAGER="cat", GIT_PAGER="cat"))
    except subprocess.TimeoutExpired:
        return "Il comando ci ha messo più di 5 minuti ed è stato interrotto."
    out = r.stdout
    m = re.search(r"__NEXUS_PWD__=(.*)\s*$", out)
    if m:
        _cwd["dir"] = m.group(1).strip()
        out = out[:m.start()]
    out = (out + r.stderr).strip()
    return f"exit {r.returncode} (cartella: {_cwd['dir']})\n{out[-3500:] or '(nessun output)'}"


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


@tool("set_mode", "Cambia modalità: 'auto' = esegui tutto senza chiedere conferma, 'manuale' = chiedi prima "
      "delle azioni importanti. Usalo quando l'utente dice 'mettiti in automode' o 'torna in manuale'.",
      {"mode": {"type": "string", "enum": ["auto", "manuale"]}}, ["mode"])
def set_mode(ctx, mode):
    on = mode == "auto"
    ctx.cfg["auto_mode"] = on
    ctx.cfg.save()
    ctx.n.bus.emit("config", config=ctx.cfg.public())
    ctx.step("⚡" if on else "🛡️", "Automode attivo" if on else "Modalità manuale")
    return "Automode attivo: non chiederò più conferme." if on else "Modalità manuale: chiederò conferma prima delle azioni importanti."
