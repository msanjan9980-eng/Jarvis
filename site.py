"""Jarvis — unified site. Single Flask app, three linked pages, one port.

Pages:
  /          Dashboard  — stats, events, conflicts, live trace, actions
  /add       Add Event  — create a real Google Calendar event
  /compose   Compose    — pick conflict, pick new time, simulate reply

Port 8000. Old UIs (webui*.py) still work as fallbacks.
"""
import io
import queue
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, redirect, render_template_string, request, url_for

from jarvis.agent import propose_only, check_only
from jarvis.calendar import list_events, find_conflicts, pick_recipient
from jarvis.email import send_proposal, send_confirmation, send_decline_acknowledgment
from jarvis.auth import get_calendar_service
from jarvis import store, config

app = Flask(__name__)

_lock = threading.Lock()
_log_q = queue.Queue()
_running = {"value": False}


# --------------------------------------------------------------------------
# Shared machinery
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Shared CSS and shell
# --------------------------------------------------------------------------

CSS = r"""
:root {
  --bg-0:#05070d; --bg-1:#0a0f1c; --bg-2:#0f172a; --bg-3:#131d33;
  --line:#1e2a44; --line-2:#243352;
  --txt-0:#e6ecf7; --txt-1:#94a3b8; --txt-2:#64748b;
  --accent:#38bdf8; --accent-2:#7dd3fc;
  --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; --info:#60a5fa;
  --shadow: 0 10px 40px -10px rgba(0,0,0,.6);
}
* { box-sizing:border-box; }
html, body { height:100%; }
body {
  margin:0; font-family:'Inter',-apple-system,BlinkMacSystemFont,ui-sans-serif,system-ui,sans-serif;
  background: radial-gradient(1200px 600px at 15% -10%, #0c1830 0%, var(--bg-0) 55%) fixed;
  color:var(--txt-0); overflow-x:hidden;
}
.mono { font-family: ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace; }

header.top {
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 26px; border-bottom:1px solid var(--line);
  background: linear-gradient(180deg, rgba(15,23,42,.9), rgba(10,15,28,.55));
  position:sticky; top:0; z-index:50; backdrop-filter:blur(8px);
}
.brand { display:flex; align-items:center; gap:14px; }
.logo {
  width:36px; height:36px; border-radius:10px;
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  display:grid; place-items:center; font-weight:800; color:#001; font-size:14px;
  box-shadow: 0 6px 22px -6px rgba(56,189,248,.6);
}
.brand h1 { font-size:15px; margin:0; letter-spacing:.2px; }
.brand .sub { font-size:11px; color:var(--txt-2); margin-top:2px; }

nav.tabs { display:flex; gap:4px; }
nav.tabs a {
  color:var(--txt-1); text-decoration:none; font-size:13px; font-weight:600;
  padding:8px 14px; border-radius:8px; transition: all .15s ease;
  border:1px solid transparent;
}
nav.tabs a:hover { color:var(--txt-0); background:rgba(30,41,59,.5); }
nav.tabs a.active { color:var(--accent-2); background:rgba(56,189,248,.10); border-color:rgba(56,189,248,.35); }

.who { display:flex; align-items:center; gap:10px; }
.chip {
  font-size:11px; color:var(--txt-1); border:1px solid var(--line);
  padding:5px 10px; border-radius:99px; background:rgba(30,41,59,.4);
}
.chip .dot { width:8px; height:8px; border-radius:99px; background:var(--ok); box-shadow:0 0 12px var(--ok); display:inline-block; margin-right:6px; }
.chip .dot.run { background: var(--warn); box-shadow:0 0 12px var(--warn); animation:pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.35 } }

.stats { display:grid; grid-template-columns: repeat(4,1fr); border-bottom:1px solid var(--line); background:rgba(10,15,28,.65); }
.stat { padding:14px 22px; border-right:1px solid var(--line); }
.stat:last-child { border-right:0; }
.stat .k { font-size:10px; color:var(--txt-2); text-transform:uppercase; letter-spacing:1.2px; }
.stat .v { font-size:24px; font-weight:700; margin-top:4px; letter-spacing:-.5px; }
.stat .v.ok { color:var(--ok); } .stat .v.warn { color:var(--warn); }
.stat .v.bad { color:var(--bad); } .stat .v.info { color:var(--info); }

.wrap { padding:22px 26px; }
h2.section {
  font-size:11px; text-transform:uppercase; letter-spacing:1.4px;
  color:var(--txt-2); margin:0 0 14px; display:flex; align-items:center; gap:10px;
}
h2.section::before { content:""; width:6px; height:6px; background:var(--accent); border-radius:2px; box-shadow:0 0 10px var(--accent); }

.ev {
  background:linear-gradient(135deg, rgba(30,41,59,.5), rgba(15,23,42,.5));
  border:1px solid var(--line); border-left:3px solid var(--warn);
  border-radius:10px; padding:12px 14px; margin-bottom:10px; transition: transform .15s ease;
}
.ev:hover { transform:translateX(2px); }
.ev .title { font-weight:600; font-size:14px; display:flex; justify-content:space-between; align-items:center; }
.ev .time { font-size:12px; color:var(--txt-1); margin-top:4px; }
.ev .cal { font-size:11px; color:var(--txt-2); margin-top:4px; }
.pill { font-size:10px; padding:2px 8px; border-radius:99px; text-transform:uppercase; letter-spacing:.8px; border:1px solid currentColor; }
.pill.warn { color:var(--warn); } .pill.ok { color:var(--ok); }
.pill.bad { color:var(--bad); } .pill.info { color:var(--info); }

.panel { background:var(--bg-2); border:1px solid var(--line); border-radius:10px; padding:18px; }
label { display:block; font-size:11px; text-transform:uppercase; letter-spacing:1.1px; color:var(--txt-2); margin:16px 0 6px; }
label:first-child { margin-top:0; }
input, select, textarea {
  width:100%; background:#0b1220; border:1px solid var(--line); color:var(--txt-0);
  padding:10px 12px; border-radius:8px; font-family:inherit; font-size:13px;
}
input:focus, select:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px rgba(56,189,248,.15); }
.row2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }

button.btn {
  appearance:none; border:1px solid var(--line-2);
  background:linear-gradient(180deg, rgba(30,41,59,.9), rgba(15,23,42,.9));
  color:var(--txt-0); font-family:inherit; font-size:13px; font-weight:600;
  padding:11px 18px; border-radius:10px; cursor:pointer; transition: all .15s ease;
  display:inline-flex; align-items:center; gap:8px;
}
button.btn:hover:not(:disabled) { border-color:var(--accent); box-shadow:0 0 0 3px rgba(56,189,248,.12); }
button.btn:disabled { opacity:.4; cursor:not-allowed; }
button.btn.primary { background:linear-gradient(180deg,#0ea5e9,#0369a1); border-color:#0284c7; color:#001; }
button.btn.danger { background:linear-gradient(180deg,#b91c1c,#7f1d1d); border-color:#991b1b; color:#fff; }
button.btn.ghost { background:transparent; }
button.btn.full { width:100%; justify-content:center; padding:13px; }

.actions {
  display:flex; gap:12px; align-items:center; flex-wrap:wrap;
  padding:14px 0; border-top:1px solid var(--line); margin-top:22px;
}
.status { font-size:12px; color:var(--txt-2); margin-left:auto; display:flex; align-items:center; gap:8px; }
.status .pulse { width:9px; height:9px; border-radius:99px; background:var(--ok); box-shadow:0 0 12px var(--ok); }
.status.running .pulse { background:var(--warn); box-shadow:0 0 12px var(--warn); animation:pulse 1.4s ease-in-out infinite; }

.trace {
  background:#04060c; border:1px solid var(--line); border-radius:12px; height:100%;
  display:flex; flex-direction:column; box-shadow:var(--shadow); overflow:hidden;
}
.trace-head {
  display:flex; align-items:center; gap:8px; padding:10px 14px;
  border-bottom:1px solid var(--line); background:rgba(15,23,42,.6);
}
.trace-head .tl { width:12px; height:12px; border-radius:99px; }
.tl.r { background:#ff5f57; } .tl.y { background:#febc2e; } .tl.g { background:#28c840; }
.trace-head .path { margin-left:10px; font-size:12px; color:var(--txt-2); }
.trace-body {
  padding:14px 18px; overflow-y:auto; flex:1; font-size:13px; line-height:1.55;
  white-space:pre-wrap; word-break:break-word; min-height:280px;
}
.ln { display:block; }
.ln.ok { color:var(--ok); } .ln.bad { color:var(--bad); } .ln.warn { color:var(--warn); }
.ln.info { color:var(--info); } .ln.dim { color:var(--txt-2); }
.ln.acc { color:var(--accent-2); } .ln.plain { color:var(--txt-0); }

.banner {
  padding:12px 16px; border-radius:8px; font-size:13px; margin-bottom:18px;
  border:1px solid;
}
.banner.ok { background:rgba(34,197,94,.1); border-color:#166534; color:#86efac; }
.banner.err { background:rgba(239,68,68,.1); border-color:#7f1d1d; color:#fca5a5; }
.banner.info { background:rgba(96,165,250,.1); border-color:#1e40af; color:#93c5fd; }
.banner.hidden { display:none; }

.grid2 { display:grid; grid-template-columns: 380px 1fr; gap:22px; height: calc(100vh - 230px); }
@media (max-width:1000px){ .grid2 { grid-template-columns:1fr; height:auto; } }
.grid3 { display:grid; grid-template-columns: 1fr 1fr; gap:22px; }
@media (max-width:1000px){ .grid3 { grid-template-columns:1fr; } }
.col { overflow-y:auto; }

.footer { padding:12px 26px; font-size:11px; color:var(--txt-2); border-top:1px solid var(--line); display:flex; justify-content:space-between; background:rgba(5,7,13,.6); }
.footer a { color:var(--txt-1); text-decoration:none; } .footer a:hover { color:var(--accent-2); }

::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#1e2a44; border-radius:99px; border:2px solid transparent; background-clip:padding-box; }
"""


def _nav(active):
    items = [("/", "Dashboard"), ("/add", "Add Event"), ("/compose", "Compose")]
    parts = []
    for href, label in items:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return '<nav class="tabs">' + "".join(parts) + "</nav>"


def _shell(title, active, body, stats_html="", extra_js=""):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{title} · Jarvis</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<style>{CSS}</style></head><body>'
        '<header class="top">'
        '  <div class="brand"><div class="logo">J</div>'
        '    <div><h1>Jarvis <span style="color:var(--txt-2);font-weight:400;">— meeting conflict resolver</span></h1>'
        '    <div class="sub">Sanjan M · CHAOS Hackathon 2026</div></div>'
        '  </div>'
        f'  {_nav(active)}'
        '  <div class="who">'
        '    <span class="chip" id="run-chip"><span class="dot" id="run-dot"></span><span id="run-txt">idle</span></span>'
        '    <span class="chip" id="clock">--:--:--</span>'
        '  </div>'
        '</header>'
        + stats_html +
        '<main class="wrap">' + body + '</main>'
        '<footer class="footer">'
        '  <div><a href="https://github.com/msanjan9980-eng/Jarvis" target="_blank">github.com/msanjan9980-eng/Jarvis</a> · 20 unit tests · 5 decision outcomes</div>'
        '  <div>local-only · never exposed on the network</div>'
        '</footer>'
        '<script>'
        'const $ = (id) => document.getElementById(id);'
        'let RUNNING=false;'
        'function setRunning(on){'
        '  RUNNING=on;'
        '  document.querySelectorAll("button.btn").forEach(b=>b.disabled=on);'
        '  $("run-dot").className = "dot" + (on?" run":"");'
        '  $("run-txt").textContent = on?"running…":"idle";'
        '}'
        'function classForLine(l){'
        '  if(l.includes("ERROR")||l.includes("declined")||l.includes("escalate"))return "bad";'
        '  if(l.includes("accept")||l.includes("moved")||l.includes("rescheduled"))return "ok";'
        '  if(l.includes("counter")||l.includes("round 2"))return "warn";'
        '  if(l.includes("no_reply")||l.includes("awaiting"))return "dim";'
        '  if(l.startsWith("[jarvis]"))return "acc";'
        '  if(l.startsWith("[ui]"))return "dim";'
        '  return "plain";'
        '}'
        'function appendRaw(s){'
        '  const el = $("log"); if(!el) return;'
        '  if(el.dataset.fresh!=="1"){el.innerHTML="";el.dataset.fresh="1";}'
        '  const lines = s.split("\\n");'
        '  for(let i=0;i<lines.length;i++){'
        '    const ln=lines[i]; if(i===lines.length-1 && ln==="")continue;'
        '    const span=document.createElement("span");'
        '    span.className="ln "+classForLine(ln); span.textContent=ln+"\\n";'
        '    el.appendChild(span);'
        '  }'
        '  el.scrollTop = el.scrollHeight;'
        '}'
        'function resetLog(){ const el=$("log"); if(!el)return; el.innerHTML=""; el.dataset.fresh="1"; }'
        'function streamLog(){'
        '  const src = new EventSource("/api/events");'
        '  src.onmessage = (e)=>{'
        '    if(e.data==="__END__"){ src.close(); setRunning(false); loadStats(); return; }'
        '    appendRaw(e.data.replace(/\\\\n/g,"\\n"));'
        '  };'
        '  src.onerror = ()=>{ src.close(); setRunning(false); };'
        '}'
        'async function loadStats(){'
        '  try{'
        '    const r = await fetch("/api/state"); const s = await r.json();'
        '    const set=(id,v)=>{ const el=$(id); if(el) el.textContent=v; };'
        '    set("s-conflicts",(s.conflicts||[]).length);'
        '    set("s-pending",(s.pending||[]).length);'
        '    set("s-resolved",s.resolved_count||0);'
        '    set("s-escalations",(s.escalations||[]).length);'
        '    if(typeof onStateLoaded === "function") onStateLoaded(s);'
        '  }catch(e){ console.error(e); }'
        '}'
        'async function runAction(action, body){'
        '  resetLog(); setRunning(true);'
        '  await fetch("/api/"+action, {method:"POST", headers:{"content-type":"application/json"}, body: JSON.stringify(body||{})});'
        '  streamLog();'
        '}'
        'function tick(){ const d=new Date(); $("clock").textContent=d.toTimeString().slice(0,8); }'
        'setInterval(tick,1000); tick();'
        'setInterval(()=>{ if(!RUNNING) loadStats(); }, 5000);'
        'loadStats();'
        + extra_js +
        '</script>'
        '</body></html>'
    )


STATS_HTML = (
    '<div class="stats">'
    '  <div class="stat"><div class="k">Conflicts detected</div><div class="v warn" id="s-conflicts">0</div></div>'
    '  <div class="stat"><div class="k">Pending proposals</div><div class="v info" id="s-pending">0</div></div>'
    '  <div class="stat"><div class="k">Rescheduled</div><div class="v ok" id="s-resolved">0</div></div>'
    '  <div class="stat"><div class="k">Escalations</div><div class="v bad" id="s-escalations">0</div></div>'
    '</div>'
)


# --------------------------------------------------------------------------
# Page: Dashboard
# --------------------------------------------------------------------------

DASHBOARD_BODY = """
<div class="grid2">
  <div class="col">
    <h2 class="section">Current calendar events</h2>
    <div id="events"><div class="ev"><div class="title">loading…</div></div></div>
    <h2 class="section" style="margin-top:26px;">Detected conflicts</h2>
    <div id="conflicts"><div class="ev"><div class="title">loading…</div></div></div>
    <div class="actions">
      <button class="btn primary" onclick="runAction('propose')">▶ Propose</button>
      <button class="btn" onclick="runAction('check', {mode:'check'})">✓ Check replies</button>
      <button class="btn ghost" onclick="runAction('reset')">↻ Reset demo state</button>
    </div>
  </div>
  <div class="col">
    <div class="trace">
      <div class="trace-head">
        <span class="tl r"></span><span class="tl y"></span><span class="tl g"></span>
        <span class="path">jarvis/agent.py — live trace</span>
      </div>
      <div class="trace-body mono" id="log"><span class="ln dim">Waiting for a task…</span></div>
    </div>
  </div>
</div>
"""

DASHBOARD_JS = """
function onStateLoaded(s){
  try{
    const ev = (s.events||[]).map(e =>
      `<div class="ev"><div class="title">${e.summary}<span class="pill info">scheduled</span></div>
       <div class="time">${e.start} → ${e.end}</div><div class="cal">${e.calendar}</div></div>`
    ).join('') || '<div class="ev"><div class="title">No upcoming events</div></div>';
    const evEl = document.getElementById("events");
    if(evEl) evEl.innerHTML = ev;
    const cf = (s.conflicts||[]).map(c =>
      `<div class="ev"><div class="title">${c.a.summary} ↔ ${c.b.summary}<span class="pill bad">overlap</span></div>
       <div class="time">${c.a.start} vs ${c.b.start}</div><div class="cal">suggested · ${c.suggested_human||"—"}</div></div>`
    ).join('') || '<div class="ev"><div class="title">No conflicts</div></div>';
    const cfEl = document.getElementById("conflicts");
    if(cfEl) cfEl.innerHTML = cf;
  }catch(e){ console.error(e); }
}
"""


# --------------------------------------------------------------------------
# Page: Add Event
# --------------------------------------------------------------------------

ADD_BODY = """
<div class="grid3">
  <div class="panel">
    <h2 class="section">Add a calendar event</h2>
    <p style="color:var(--txt-1); font-size:13px; margin:0 0 4px;">Writes to your primary Google Calendar. The agent picks it up on next run.</p>

    <label>Event title</label>
    <input id="summary" placeholder="e.g. Client call" autofocus>

    <div class="row2">
      <div><label>Date</label><input type="date" id="date"></div>
      <div><label>Start time</label><input type="time" id="start" value="10:00"></div>
    </div>

    <label>Duration (minutes)</label>
    <select id="duration"><option>15</option><option>30</option><option selected>45</option><option>60</option><option>90</option><option>120</option></select>

    <label>Guests (optional, comma-separated)</label>
    <input id="attendees" placeholder="priya@example.com, sam@example.com">

    <div class="actions">
      <button class="btn primary full" onclick="createEvent()">Create event</button>
    </div>
    <div id="banner" class="banner hidden"></div>
  </div>

  <div>
    <h2 class="section">Existing events</h2>
    <div id="events-list"><div class="ev"><div class="title">loading…</div></div></div>
    <div style="margin-top:18px;">
      <a href="/compose" class="btn" style="text-decoration:none;">→ Go to Compose</a>
    </div>
  </div>
</div>
"""

ADD_JS = """
function setBanner(kind, msg){
  const el = document.getElementById('banner');
  el.className = 'banner ' + kind;
  el.textContent = msg;
}
function onStateLoaded(s){
  const ev = (s.events||[]).map(e =>
    `<div class="ev"><div class="title">${e.summary}</div>
     <div class="time">${e.start} → ${e.end}</div><div class="cal">${e.calendar}</div></div>`
  ).join('') || '<div class="ev"><div class="title">No upcoming events</div></div>';
  document.getElementById('events-list').innerHTML = ev;
}
async function createEvent(){
  const body = {
    summary: document.getElementById('summary').value.trim(),
    date: document.getElementById('date').value,
    start: document.getElementById('start').value,
    duration: parseInt(document.getElementById('duration').value,10),
    attendees: document.getElementById('attendees').value.split(',').map(s=>s.trim()).filter(Boolean),
  };
  if(!body.summary || !body.date || !body.start){
    setBanner('err','Please fill title, date, and start time.'); return;
  }
  setRunning(true); setBanner('info','Creating…');
  try{
    const r = await fetch('/api/add', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(body)});
    const j = await r.json();
    if(j.ok){ setBanner('ok','Created: '+j.summary+' on '+j.start); document.getElementById('summary').value=''; document.getElementById('attendees').value=''; }
    else setBanner('err','Error: '+j.error);
  }catch(e){ setBanner('err','Error: '+e.message); }
  setRunning(false); loadStats();
}
(function(){ const t=new Date(); t.setDate(t.getDate()+1); document.getElementById('date').value=t.toISOString().slice(0,10); })();
"""


# --------------------------------------------------------------------------
# Page: Compose
# --------------------------------------------------------------------------

COMPOSE_BODY = """
<div class="grid3">
  <div class="panel">
    <h2 class="section">Compose a proposal</h2>

    <label>Pick a conflict</label>
    <select id="conflict"></select>

    <label>New start time</label>
    <input type="datetime-local" id="new-start">

    <div class="actions">
      <button class="btn primary full" onclick="sendProposal()">Confirm &amp; send proposal</button>
    </div>

    <label>Simulate or read a reply</label>
    <select id="sim-mode">
      <option value="check">Read replies from Gmail (real)</option>
      <option value="accept">Simulate: accept</option>
      <option value="decline">Simulate: decline</option>
      <option value="unclear">Simulate: unclear</option>
    </select>
    <div class="actions">
      <button class="btn full" onclick="runCheck()">Run check</button>
    </div>

    <div id="banner" class="banner hidden"></div>
  </div>

  <div>
    <div class="trace">
      <div class="trace-head">
        <span class="tl r"></span><span class="tl y"></span><span class="tl g"></span>
        <span class="path">jarvis/agent.py — live trace</span>
      </div>
      <div class="trace-body mono" id="log"><span class="ln dim">Waiting for a task…</span></div>
    </div>
  </div>
</div>
"""

COMPOSE_JS = """
let CONFLICTS = [];
function setBanner(kind, msg){
  const el = document.getElementById('banner');
  el.className = 'banner ' + kind;
  el.textContent = msg;
}
function onStateLoaded(s){
  CONFLICTS = s.conflicts || [];
  const sel = document.getElementById('conflict');
  sel.innerHTML = CONFLICTS.map((c,i) =>
    `<option value="${i}">[${c.a.summary}] ${c.a.start} vs [${c.b.summary}] ${c.b.start}</option>`
  ).join('') || '<option>no conflicts — add an event first</option>';
  const ns = document.getElementById('new-start');
  if(!ns.value && CONFLICTS.length) ns.value = CONFLICTS[0].suggested_start || '';
}
async function sendProposal(){
  if(!CONFLICTS.length){ setBanner('err','No conflicts available.'); return; }
  const idx = parseInt(document.getElementById('conflict').value,10);
  const ns = document.getElementById('new-start').value;
  if(!ns){ setBanner('err','Pick a new start time.'); return; }
  setBanner('info','Sending…');
  await runAction('compose-propose', {conflict_index: idx, new_start: ns});
  setBanner('ok','Proposal sent. Reply in Gmail, then run check.');
}
async function runCheck(){
  const mode = document.getElementById('sim-mode').value;
  await runAction('check', {mode});
}
"""


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/")
def page_dashboard():
    return render_template_string(_shell("Dashboard", "/", DASHBOARD_BODY, STATS_HTML, DASHBOARD_JS))


@app.get("/add")
def page_add():
    return render_template_string(_shell("Add Event", "/add", ADD_BODY, STATS_HTML, ADD_JS))


@app.get("/compose")
def page_compose():
    return render_template_string(_shell("Compose", "/compose", COMPOSE_BODY, STATS_HTML, COMPOSE_JS))


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get("/api/state")
def api_state():
    events = list_events()
    conflicts = find_conflicts(events)

    event_cards = [{
        "summary": e["summary"],
        "start": e["start"].strftime("%a %H:%M"),
        "end": e["end"].strftime("%H:%M"),
        "calendar": e["calendar"],
    } for e in events]

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
            "suggested_start": suggested.strftime("%Y-%m-%dT%H:%M"),
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


@app.post("/api/propose")
def api_propose():
    _run(propose_only)
    return {"ok": True}


@app.post("/api/compose-propose")
def api_compose_propose():
    data = request.get_json(force=True)
    idx = int(data.get("conflict_index", 0))
    new_start_iso = data.get("new_start")

    def task():
        events = list_events()
        conflicts = find_conflicts(events)
        if not conflicts:
            print("[ui] no conflicts to propose."); return
        idx_safe = max(0, min(idx, len(conflicts) - 1))
        a, b = conflicts[idx_safe]
        new_start = datetime.fromisoformat(new_start_iso)
        duration = a["end"] - a["start"]
        new_end = new_start + duration
        recipient = pick_recipient(a, config.my_email())
        print(f"[ui] recipient: {recipient}")
        msg_id = send_proposal(recipient, a, new_start, new_end)
        print(f"[ui] sent id={msg_id} for '{a['summary']}' -> {new_start:%a %d %b %H:%M}")
        store.add_pending({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
            "recipient": recipient,
        })

    _run(task)
    return {"ok": True}


@app.post("/api/check")
def api_check():
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "check")

    def task():
        if mode == "check":
            check_only()
            return
        # simulated reply
        pending = store.pending_only()
        if not pending:
            print("[ui] no pending proposals to simulate against."); return
        from jarvis.parse import parse_reply
        fake = {"accept": "Yes", "decline": "No", "unclear": "maybe later"}[mode]
        for p in pending:
            new_start = datetime.fromisoformat(p["new_start_iso"])
            print(f"[ui] simulating '{fake}' for '{p['summary']}'")
            d = parse_reply(fake, reference_date=new_start)
            print(f"[ui]   parsed -> {d['decision']}")
            if d["decision"] == "accept":
                svc = get_calendar_service()
                ev = svc.events().get(calendarId=p["calendar_id"], eventId=p["event_id"]).execute()
                old_start = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
                old_end = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
                dur = old_end - old_start
                svc.events().patch(
                    calendarId=p["calendar_id"], eventId=p["event_id"],
                    body={"start": {"dateTime": new_start.isoformat(), "timeZone": "Asia/Kolkata"},
                          "end": {"dateTime": (new_start + dur).isoformat(), "timeZone": "Asia/Kolkata"}},
                ).execute()
                store.mark_resolved(p["proposal_msg_id"], "rescheduled")
                print(f"[ui] moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
                try:
                    recipient = p.get("recipient") or config.my_email()
                    send_confirmation(recipient, p["summary"], new_start, new_start + dur,
                                      in_reply_to_msg_id=p.get("proposal_msg_id"))
                    print(f"[ui] sent confirmation to {recipient}")
                except Exception as e:
                    print(f"[ui] confirmation send failed: {e!r}")
            elif d["decision"] == "decline":
                try:
                    recipient = p.get("recipient") or config.my_email()
                    send_decline_acknowledgment(recipient, p["summary"],
                                                in_reply_to_msg_id=p.get("proposal_msg_id"))
                    print(f"[ui] sent decline acknowledgment to {recipient}")
                except Exception as e:
                    print(f"[ui] decline acknowledgment failed: {e!r}")
                store.mark_resolved(p["proposal_msg_id"], "declined")
                store.log_escalation({"event": p["summary"], "reason": "declined", "proposal_msg_id": p["proposal_msg_id"]})
            else:
                store.mark_resolved(p["proposal_msg_id"], "escalated")
                store.log_escalation({"event": p["summary"], "reason": "unclear", "raw": fake, "proposal_msg_id": p["proposal_msg_id"]})

    _run(task)
    return {"ok": True}


@app.post("/api/reset")
def api_reset():
    def task():
        print("[ui] resetting demo state")
        for script in ("reset_calendar.py", "seed_calendar.py"):
            print(f"[ui] running {script}")
            r = subprocess.run([sys.executable, script], capture_output=True, text=True)
            print(r.stdout or "", end="")
            if r.stderr:
                print(r.stderr)
    _run(task)
    return {"ok": True}


@app.post("/api/add")
def api_add():
    data = request.get_json(force=True)
    try:
        summary = data["summary"].strip()
        date_str = data["date"]
        start_str = data["start"]
        duration = int(data.get("duration", 45))
        attendees = [a for a in data.get("attendees", []) if a]

        start = datetime.fromisoformat(f"{date_str}T{start_str}:00")
        end = start + timedelta(minutes=duration)
        tz = "+05:30"

        body = {
            "summary": summary,
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S") + tz, "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S") + tz, "timeZone": "Asia/Kolkata"},
        }
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        svc = get_calendar_service()
        created = svc.events().insert(calendarId="primary", body=body).execute()
        return jsonify({"ok": True, "id": created["id"], "summary": created.get("summary", summary),
                        "start": start.strftime("%a %d %b %H:%M")})
    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)})


@app.get("/api/events")
def api_events():
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
    print("Jarvis site -> http://127.0.0.1:8000")
    print("Pages: / (dashboard)  /add (add event)  /compose (compose proposal)")
    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
