"""Gestione finestre su KDE Plasma (Wayland) tramite script KWin caricati via D-Bus.

Elenca, attiva, affianca (sinistra/destra/quarti), massimizza, riduce a icona e chiude finestre.
I risultati tornano indietro tramite il journal (print dello script con un marcatore unico).
"""
import json
import re
import subprocess
import time
import uuid

from . import tool
from ..config import CACHE

QDBUS = "qdbus6"

# trova le finestre che corrispondono alla richiesta (titolo o nome dell'app)
_MATCH_JS = r"""
function norm(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9àèéìòù]+/g, " ").trim(); }
function matches(w, q) {
  var hay = " " + norm(w.caption) + " " + norm(w.resourceClass) + " " + norm(w.resourceName) + " ";
  var words = norm(q).split(" ").filter(function (x) { return x.length > 0; });
  if (!words.length) return false;
  for (var i = 0; i < words.length; i++) if (hay.indexOf(words[i]) < 0) return false;
  return true;
}
function normalWindows() {
  var r = [], ws = workspace.windowList();
  for (var i = 0; i < ws.length; i++) {
    var w = ws[i];
    if (w.normalWindow && !w.skipTaskbar && w.resourceClass !== "nexus-ui") r.push(w);
  }
  return r;
}
function find(q) {
  var ws = normalWindows(), best = null;
  for (var i = 0; i < ws.length; i++) if (matches(ws[i], q)) { best = ws[i]; if (ws[i] === workspace.activeWindow) break; }
  return best;
}
function info(w) { return { title: w.caption, app: w.resourceClass, min: w.minimized, active: w === workspace.activeWindow }; }
"""


def run_kwin(body):
    """Esegue codice JS dentro KWin e ritorna l'oggetto stampato con out(...)."""
    tag = "NEXUS" + uuid.uuid4().hex[:10]
    js = _MATCH_JS + f'\nfunction out(o) {{ print("{tag} " + JSON.stringify(o)); }}\ntry {{\n{body}\n}} catch (e) {{ out({{error: String(e)}}); }}\n'
    path = CACHE / f"{tag}.js"
    path.write_text(js)
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 1))
    try:
        sid = subprocess.run([QDBUS, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript",
                              str(path), tag], capture_output=True, text=True, timeout=10).stdout.strip()
        if not sid.lstrip("-").isdigit() or int(sid) < 0:
            raise RuntimeError("KWin non ha caricato lo script")
        subprocess.run([QDBUS, "org.kde.KWin", f"/Scripting/Script{sid}", "org.kde.kwin.Script.run"],
                       capture_output=True, timeout=10)
        for _ in range(20):
            time.sleep(0.1)
            log = subprocess.run(["journalctl", "--user", "--since", since, "--no-pager", "-o", "cat"],
                                 capture_output=True, text=True, timeout=10).stdout
            m = re.search(rf"{tag} (.*)", log)
            if m:
                return json.loads(m.group(1))
        return None
    finally:
        subprocess.run([QDBUS, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", tag],
                       capture_output=True, timeout=10)
        path.unlink(missing_ok=True)


def _ensure_open(ctx, app):
    """Se la finestra non c'è, apre l'app e aspetta che compaia."""
    q = json.dumps(app)
    if run_kwin(f"out(find({q}) ? 1 : 0);") == 1:
        return True
    from .apps import find_app
    a = find_app(app, ctx.cfg)
    if not a:
        return False
    ctx.step("🚀", f"Apro {a['name']}")
    subprocess.Popen(["gtk-launch", a["id"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(20):
        time.sleep(0.6)
        if run_kwin(f"out(find({q}) || find({json.dumps(a['name'])}) ? 1 : 0);") == 1:
            return True
    return False


# posizioni: frazioni (x, y, larghezza, altezza) dell'area utile dello schermo
POSITIONS = {
    "sinistra": (0, 0, .5, 1), "destra": (.5, 0, .5, 1), "alto": (0, 0, 1, .5), "basso": (0, .5, 1, .5),
    "alto-sinistra": (0, 0, .5, .5), "alto-destra": (.5, 0, .5, .5),
    "basso-sinistra": (0, .5, .5, .5), "basso-destra": (.5, .5, .5, .5),
    "centro": (.15, .1, .7, .8),
}


def _place_js(app, pos):
    fx, fy, fw, fh = POSITIONS[pos]
    return f"""
var w = find({json.dumps(app)});
if (!w) {{ out({{ok: false}}); }} else {{
  w.minimized = false;
  if (w.fullScreen) w.fullScreen = false;
  w.setMaximize(false, false);
  var a = workspace.clientArea(KWin.MaximizeArea, w);
  w.frameGeometry = {{ x: a.x + a.width * {fx}, y: a.y + a.height * {fy}, width: a.width * {fw}, height: a.height * {fh} }};
  workspace.activeWindow = w;
  out({{ok: true, title: w.caption}});
}}"""


@tool("list_windows", "Elenca le finestre aperte (titolo e app).")
def list_windows(ctx):
    ctx.step("🪟", "Guardo le finestre aperte")
    res = run_kwin("var ws = normalWindows(), r = []; for (var i = 0; i < ws.length; i++) r.push(info(ws[i])); out(r);")
    if not res:
        return "Non ci sono finestre aperte."
    return "; ".join(f"{w['title']} ({w['app']}{', ridotta' if w['min'] else ''}{', attiva' if w['active'] else ''})"
                     for w in res)


@tool("place_window", "Sposta una finestra in una zona dello schermo: sinistra, destra, alto, basso, "
      "alto-sinistra, alto-destra, basso-sinistra, basso-destra, centro. Se l'app non è aperta la apre.",
      {"app": {"type": "string", "description": "nome dell'app o parte del titolo, es. firefox, writer"},
       "position": {"type": "string", "enum": list(POSITIONS)}}, ["app", "position"])
def place_window(ctx, app, position):
    if position not in POSITIONS:
        return f"Posizione sconosciuta: {position}"
    if not _ensure_open(ctx, app):
        return f"Non trovo né riesco ad aprire '{app}'."
    ctx.step("🪟", f"Metto {app} a {position}")
    r = run_kwin(_place_js(app, position))
    return f"Ho messo “{r['title']}” a {position}." if r and r.get("ok") else f"Non trovo la finestra di '{app}'."


@tool("split_screen", "Affianca due app: una a sinistra e una a destra (le apre se servono).",
      {"left": {"type": "string"}, "right": {"type": "string"}}, ["left", "right"])
def split_screen(ctx, left, right):
    msgs = [place_window(ctx, left, "sinistra"), place_window(ctx, right, "destra")]
    return " ".join(msgs)


@tool("window_action", "Agisce su una finestra: attiva (portala davanti), massimizza, riduci (a icona), "
      "ripristina, schermo_intero, chiudi.",
      {"app": {"type": "string"},
       "action": {"type": "string", "enum": ["attiva", "massimizza", "riduci", "ripristina", "schermo_intero", "chiudi"]}},
      ["app", "action"])
def window_action(ctx, app, action):
    q = json.dumps(app)
    if action == "chiudi" and not ctx.confirm(f"Chiudo la finestra di {app}? Se c'è lavoro non salvato potresti perderlo."):
        return "L'utente non ha voluto chiudere la finestra."
    code = {
        "attiva": "w.minimized = false; workspace.activeWindow = w;",
        "massimizza": "w.minimized = false; w.setMaximize(true, true); workspace.activeWindow = w;",
        "riduci": "w.minimized = true;",
        "ripristina": "w.minimized = false; w.setMaximize(false, false); workspace.activeWindow = w;",
        "schermo_intero": "w.minimized = false; w.fullScreen = !w.fullScreen; workspace.activeWindow = w;",
        "chiudi": "w.closeWindow();",
    }.get(action)
    if not code:
        return f"Azione sconosciuta: {action}"
    ctx.step("🪟", f"{action.replace('_', ' ').capitalize()}: {app}")
    r = run_kwin(f"var w = find({q}); if (!w) out({{ok:false}}); else {{ var t = w.caption; {code} out({{ok:true, title:t}}); }}")
    return f"Fatto ({action}) su “{r['title']}”." if r and r.get("ok") else f"Non trovo nessuna finestra di '{app}'."
