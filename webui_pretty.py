"""Jarvis — premium dashboard UI. Port 8002. Standalone. Zero dependencies.

Does not touch jarvis/*. Uses the same pipeline functions as webui.py and webui_form.py.
"""
import io
import json
import os
import queue
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, render_template_string, request

from jarvis.calendar import list_events, find_conflicts
from jarvis.email import send_proposal
from jarvis.auth import get_calendar_service
from jarvis import store
from jarvis import config

app = Flask(__name__)
MY_EMAIL = config.my_email()

_lock = threading.Lock()
_log_q = queue.Queue()
_running = {"value": False}
_started_at = datetime.now()


class _Tee(io.TextIOBase):
    def __init__(self, original, q):
        self.original = original
        self.q = q

    def write(self, s):
        if s:
            self.original.write(s)
            self.q.put(s)
        return len(s or "")

    def flush(self):
        self.original.flush()


def _run(fn):
    with _lock:
        if _running["value"]:
            _log_q.put("\n[ui] a task is already running\n")
            return
        _running["value"] = True

    def worker():
        try:
            with redirect_stdout(_Tee(sys.stdout, _log_q)):
                fn()
        except Exception as e:
            _log_q.put(f"\n[ui] ERROR: {e!r}\n")
        finally:
            _log_q.put("\n[ui] --- task finished ---\n")
            _running["value"] = False

    threading.Thread(target=worker, daemon=True).start()


PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Jarvis — CHAOS Hackathon 2026</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --bg-0:#05070d; --bg-1:#0a0f1c; --bg-2:#0f172a; --bg-3:#131d33;
    --line:#1e2a44; --line-2:#243352;
    --txt-0:#e6ecf7; --txt-1:#94a3b8; --txt-2:#64748b;
    --accent:#38bdf8; --accent-2:#7dd3fc;
    --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; --info:#60a5fa; --counter:#a78bfa;
    --shadow: 0 10px 40px -10px rgba(0,0,0,.6);
  }
  * { box-sizing: border-box; }
  html, body { height:100%; }
  body {
    margin:0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, ui-sans-serif, system-ui, sans-serif;
    background: radial-gradient(1200px 600px at 15% -10%, #0c1830 0%, var(--bg-0) 55%) fixed;
    color: var(--txt-0); overflow-x:hidden;
  }
  .mono { font-family: ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace; }

  /* Header */
  header.top {
    display:flex; align-items:center; justify-content:space-between;
    padding: 18px 28px; border-bottom:1px solid var(--line);
    background: linear-gradient(180deg, rgba(15,23,42,.9), rgba(10,15,28,.6));
    position: sticky; top:0; z-index: 50; backdrop-filter: blur(8px);
  }
  .brand { display:flex; align-items:center; gap:14px; }
  .logo {
    width:38px; height:38px; border-radius:10px;
    background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
    display:grid; place-items:center; font-weight:800; color:#001; font-size:15px;
    box-shadow: 0 6px 22px -6px rgba(56,189,248,.6);
  }
  .brand h1 { font-size:16px; margin:0; letter-spacing:.2px; }
  .brand .sub { font-size:11px; color:var(--txt-2); margin-top:2px; }
  .who { display:flex; align-items:center; gap:14px; }
  .who .chip {
    font-size:11px; color:var(--txt-1); border:1px solid var(--line);
    padding:5px 10px; border-radius:99px; background:rgba(30,41,59,.4);
  }
  .who .dot { width:8px; height:8px; border-radius:99px; background:var(--ok); box-shadow:0 0 12px var(--ok); display:inline-block; margin-right:6px; }

  /* Stat strip */
  .stats {
    display:grid; grid-template-columns: repeat(4, 1fr); gap:0;
    border-bottom:1px solid var(--line);
    background: linear-gradient(180deg, rgba(10,15,28,.85), rgba(10,15,28,.55));
  }
  .stat { padding:16px 22px; border-right:1px solid var(--line); }
  .stat:last-child { border-right:0; }
  .stat .k { font-size:11px; color:var(--txt-2); text-transform:uppercase; letter-spacing:1.2px; }
  .stat .v { font-size:26px; font-weight:700; margin-top:6px; letter-spacing:-.5px; }
  .stat .v.ok { color: var(--ok); }
  .stat .v.warn { color: var(--warn); }
  .stat .v.bad { color: var(--bad); }
  .stat .v.info { color: var(--info); }

  /* Main grid */
  main { display:grid; grid-template-columns: 400px 1fr; gap:0; height: calc(100vh - 210px); }
  @media (max-width: 1000px) { main { grid-template-columns: 1fr; height:auto; } }

  .col { padding: 22px 24px; overflow-y:auto; }
  .col.left { border-right:1px solid var(--line); background:rgba(10,15,28,.5); }
  .col.right { background: linear-gradient(180deg, rgba(15,23,42,.35), rgba(5,7,13,.6)); }

  h2.section {
    font-size:12px; text-transform:uppercase; letter-spacing:1.4px;
    color: var(--txt-2); margin:0 0 14px; display:flex; align-items:center; gap:10px;
  }
  h2.section::before { content:""; width:6px; height:6px; background:var(--accent); border-radius:2px; box-shadow:0 0 10px var(--accent); }

  /* Event cards */
  .ev {
    background: linear-gradient(135deg, rgba(30,41,59,.5), rgba(15,23,42,.5));
    border:1px solid var(--line); border-left:3px solid var(--warn);
    border-radius:10px; padding:12px 14px; margin-bottom:10px;
    transition: transform .15s ease, border-color .15s ease;
  }
  .ev:hover { transform: translateX(2px); border-color:var(--line-2); }
  .ev .title { font-weight:600; font-size:14px; display:flex; justify-content:space-between; align-items:center; }
  .ev .time { font-size:12px; color:var(--txt-1); margin-top:4px; }
  .ev .cal { font-size:11px; color:var(--txt-2); margin-top:4px; }
  .pill {
    font-size:10px; padding:2px 8px; border-radius:99px; text-transform:uppercase; letter-spacing:.8px;
    border:1px solid currentColor;
  }
  .pill.warn { color: var(--warn); }
  .pill.ok { color: var(--ok); }
  .pill.bad { color: var(--bad); }
  .pill.info { color: var(--info); }

  /* Trace panel */
  .trace {
    background: #04060c;
    border:1px solid var(--line);
    border-radius:12px;
    padding: 0;
    height: 100%;
    display:flex; flex-direction:column;
    box-shadow: var(--shadow);
    overflow:hidden;
  }
  .trace-head {
    display:flex; align-items:center; gap:8px;
    padding: 10px 14px; border-bottom:1px solid var(--line);
    background: rgba(15,23,42,.6);
  }
  .trace-head .tl { width:12px; height:12px; border-radius:99px; }
  .tl.r { background:#ff5f57; } .tl.y { background:#febc2e; } .tl.g { background:#28c840; }
  .trace-head .path { margin-left:10px; font-size:12px; color:var(--txt-2); }
  .trace-body {
    padding: 14px 18px; overflow-y:auto; flex:1; font-size:13px; line-height:1.55;
    white-space: pre-wrap; word-break: break-word;
  }
  .ln { display:block; }
  .ln.ok { color: var(--ok); }
  .ln.bad { color: var(--bad); }
  .ln.warn { color: var(--warn); }
  .ln.info { color: var(--info); }
  .ln.dim { color: var(--txt-2); }
  .ln.acc { color: var(--accent-2); }
  .ln.plain { color: var(--txt-0); }

  /* Bottom action bar */
  .actions {
    position: sticky; bottom:0; z-index:40;
    display:flex; gap:12px; align-items:center;
    padding: 14px 26px;
    border-top:1px solid var(--line);
    background: linear-gradient(0deg, rgba(10,15,28,.95), rgba(10,15,28,.7));
    backdrop-filter: blur(8px);
  }
  button.btn {
    appearance:none; border:1px solid var(--line-2);
    background: linear-gradient(180deg, rgba(30,41,59,.9), rgba(15,23,42,.9));
    color: var(--txt-0); font-family: inherit; font-size:13px; font-weight:600;
    padding: 11px 18px; border-radius:10px; cursor:pointer;
    transition: transform .1s ease, border-color .15s ease, box-shadow .15s ease;
    display:inline-flex; align-items:center; gap:8px;
  }
  button.btn:hover { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(56,189,248,.12); }
  button.btn:active { transform: translateY(1px); }
  button.btn:disabled { opacity:.4; cursor:not-allowed; }

  button.btn.primary { background: linear-gradient(180deg, #0ea5e9, #0369a1); border-color:#0284c7; color:#001; }
  button.btn.danger { background: linear-gradient(180deg, #b91c1c, #7f1d1d); border-color:#991b1b; }
  button.btn.ghost { background: transparent; }

  .status { font-size:12px; color: var(--txt-2); margin-left:auto; display:flex; align-items:center; gap:8px; }
  .status .pulse {
    width:9px; height:9px; border-radius:99px; background: var(--ok);
    box-shadow: 0 0 12px var(--ok);
  }
  .status.running .pulse { background: var(--warn); box-shadow:0 0 12px var(--warn); animation: pulse 1.4s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }

  .footer {
    padding: 12px 26px; font-size:11px; color:var(--txt-2);
    border-top:1px solid var(--line); display:flex; justify-content:space-between;
    background: rgba(5,7,13,.6);
  }
  .footer a { color: var(--txt-1); text-decoration:none; }
  .footer a:hover { color: var(--accent-2); }

  ::-webkit-scrollbar { width:10px; height:10px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background:#1e2a44; border-radius:99px; border:2px solid transparent; background-clip: padding-box; }
  ::-webkit-scrollbar-thumb:hover { background:#2a3a5c; background-clip: padding-box; }
</style>
</head>
<body>

<header class="top">
  <div class="brand">
    <div class="logo">J</div>
    <div>
      <h1>Jarvis <span style="color:var(--txt-2); font-weight:400;">— meeting conflict resolver</span></h1>
      <div class="sub">Sanjan M &nbsp;·&nbsp; CHAOS Hackathon 2026</div>
    </div>
  </div>
  <div class="who">
    <span class="chip"><span class="dot"></span>local · port 8002</span>
    <span class="chip" id="clock">--:--:--</span>
  </div>
</header>

<div class="stats">
  <div class="stat"><div class="k">Conflicts detected</div><div class="v warn" id="s-conflicts">0</div></div>
  <div class="stat"><div class="k">Pending proposals</div><div class="v info" id="s-pending">0</div></div>
  <div class="stat"><div class="k">Rescheduled</div><div class="v ok" id="s-resolved">0</div></div>
  <div class="stat"><div class="k">Escalations</div><div class="v bad" id="s-escalations">0</div></div>
</div>

<main>
  <div class="col left">
    <h2 class="section">Current calendar events</h2>
    <div id="events"><div class="ev"><div class="title">loading…</div></div></div>

    <h2 class="section" style="margin-top:26px;">Detected conflicts</h2>
    <div id="conflicts"><div class="ev"><div class="title">loading…</div></div></div>
  </div>

  <div class="col right">
    <div class="trace">
      <div class="trace-head">
        <span class="tl r"></span><span class="tl y"></span><span class="tl g"></span>
        <span class="path">jarvis/agent.py — live trace</span>
      </div>
      <div class="trace-body mono" id="log"><span class="ln dim">Waiting for a task…</span></div>
    </div>
  </div>
</main>

<div class="actions">
  <button class="btn primary" id="btn-propose">▶ Propose</button>
  <button class="btn" id="btn-check">✓ Check replies</button>
  <button class="btn ghost" id="btn-reset">↻ Reset demo state</button>
  <div class="status" id="status"><span class="pulse"></span><span id="status-txt">idle</span></div>
</div>

<div class="footer">
  <div>github.com/msanjan9980-eng/Jarvis &nbsp;·&nbsp; 20 unit tests &nbsp;·&nbsp; 4 decision outcomes</div>
  <div>local-only &nbsp;·&nbsp; never exposed on the network</div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let running = false;

function setRunning(on) {
  running = on;
  ['btn-propose','btn-check','btn-reset'].forEach(id => $(id).disabled = on);
  $('status').classList.toggle('running', on);
  $('status-txt').textContent = on ? 'running…' : 'idle';
}

function classForLine(line) {
  if (line.includes('ERROR') || line.includes('declined') || line.includes('escalate')) return 'bad';
  if (line.includes('accept') || line.includes('moved') || line.includes('rescheduled')) return 'ok';
  if (line.includes('counter') || line.includes('round 2')) return 'warn';
  if (line.includes('no_reply') || line.includes('awaiting')) return 'dim';
  if (line.startsWith('[jarvis]')) return 'acc';
  if (line.startsWith('[ui]')) return 'dim';
  return 'plain';
}

function appendRaw(s) {
  const el = $('log');
  if (el.dataset.fresh !== '1') { el.innerHTML = ''; el.dataset.fresh = '1'; }
  const lines = s.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    if (i === lines.length - 1 && ln === '') continue;
    const span = document.createElement('span');
    span.className = 'ln ' + classForLine(ln);
    span.textContent = ln + '\n';
    el.appendChild(span);
  }
  el.scrollTop = el.scrollHeight;
}

function resetLog() {
  const el = $('log');
  el.innerHTML = '';
  el.dataset.fresh = '1';
}

function stream() {
  const src = new EventSource('/events');
  src.onmessage = (e) => {
    if (e.data === '__END__') { src.close(); setRunning(false); loadState(); return; }
    appendRaw(e.data.replace(/\\\\n/g, '\\n'));
  };
  src.onerror = () => { src.close(); setRunning(false); };
}

async function loadState() {
  try {
    const r = await fetch('/api/state');
    const s = await r.json();

    $('s-conflicts').textContent = (s.conflicts || []).length;
    $('s-pending').textContent = (s.pending || []).length;
    $('s-resolved').textContent = s.resolved_count || 0;
    $('s-escalations').textContent = (s.escalations || []).length;

    const evHtml = (s.events || []).map(e =>
      `<div class="ev">
        <div class="title">${e.summary}<span class="pill ${e.pill || 'warn'}">${e.pill_text || 'event'}</span></div>
        <div class="time">${e.start} → ${e.end}</div>
        <div class="cal">${e.calendar}</div>
      </div>`
    ).join('') || '<div class="ev"><div class="title">No upcoming events</div></div>';
    $('events').innerHTML = evHtml;

    const cHtml = (s.conflicts || []).map(c =>
      `<div class="ev">
        <div class="title">${c.a.summary} ↔ ${c.b.summary}<span class="pill bad">overlap</span></div>
        <div class="time">${c.a.start} vs ${c.b.start}</div>
        <div class="cal">suggested slot · ${c.suggested_human || '—'}</div>
      </div>`
    ).join('') || '<div class="ev"><div class="title">No conflicts</div></div>';
    $('conflicts').innerHTML = cHtml;
  } catch (e) {
    console.error(e);
  }
}

async function run(action) {
  resetLog();
  setRunning(true);
  await fetch('/run/' + action, {method:'POST'});
  stream();
}

$('btn-propose').onclick = () => run('propose');
$('btn-check').onclick = () => run('check');
$('btn-reset').onclick = () => run('reset');

function tick() {
  const d = new Date();
  $('clock').textContent = d.toTimeString().slice(0,8);
}
setInterval(tick, 1000); tick();

loadState();
setInterval(() => { if (!running) loadState(); }, 5000);
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/state")
def api_state():
    events = list_events()
    conflicts = find_conflicts(events)

    event_cards = []
    for e in events:
        event_cards.append({
            "summary": e["summary"],
            "start": e["start"].strftime("%a %H:%M"),
            "end": e["end"].strftime("%H:%M"),
            "calendar": e["calendar"],
            "pill": "info",
            "pill_text": "scheduled",
        })

    conflict_cards = []
    for a, b in conflicts:
        later_end = max(a["end"], b["end"])
        base = later_end + timedelta(minutes=15)
        minute = 0 if base.minute < 30 else 30
        suggested = base.replace(minute=minute, second=0, microsecond=0)
        if suggested < base:
            suggested += timedelta(minutes=30)
        conflict_cards.append({
            "a": {"summary": a["summary"], "start": a["start"].strftime("%a %H:%M")},
            "b": {"summary": b["summary"], "start": b["start"].strftime("%a %H:%M")},
            "suggested_human": suggested.strftime("%a %d %b %H:%M"),
        })

    all_pending = store.load_pending()
    pending = [e for e in all_pending if e.get("status") == "pending"]
    resolved = [e for e in all_pending if e.get("status") == "rescheduled"]
    escalations = store.list_escalations()

    return jsonify({
        "events": event_cards,
        "conflicts": conflict_cards,
        "pending": pending,
        "resolved_count": len(resolved),
        "escalations": escalations,
    })


@app.post("/run/propose")
def run_propose():
    from jarvis.agent import propose_only
    _run(propose_only)
    return {"ok": True}


@app.post("/run/check")
def run_check():
    from jarvis.agent import check_only
    _run(check_only)
    return {"ok": True}


@app.post("/run/reset")
def run_reset():
    def task():
        print("[ui] running reset_calendar.py")
        r = subprocess.run([sys.executable, "reset_calendar.py"], capture_output=True, text=True)
        print(r.stdout or "", end="")
        if r.stderr:
            print(r.stderr)
        print("[ui] running seed_calendar.py")
        r = subprocess.run([sys.executable, "seed_calendar.py"], capture_output=True, text=True)
        print(r.stdout or "", end="")
        if r.stderr:
            print(r.stderr)
    _run(task)
    return {"ok": True}


@app.get("/events")
def events():
    def gen():
        idle = 0
        while True:
            try:
                chunk = _log_q.get(timeout=0.5)
                idle = 0
                yield f"data: {chunk.replace(chr(10), '\\\\n')}\n\n"
                if "task finished" in chunk:
                    yield "data: __END__\n\n"
                    return
            except queue.Empty:
                idle += 1
                yield ": keepalive\n\n"
                if idle > 240:
                    yield "data: __END__\n\n"
                    return
    return Response(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Jarvis dashboard -> http://127.0.0.1:8002")
    app.run(host="127.0.0.1", port=8002, debug=False, threaded=True)
