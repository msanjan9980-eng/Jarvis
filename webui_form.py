"""Form-based UI for Jarvis. Pick event, pick time, click confirm.

Additive. The CLI still works. webui.py still works.
"""
import io
import queue
import sys
import threading
from contextlib import redirect_stdout
from datetime import datetime, timedelta

from flask import Flask, Response, jsonify, render_template_string, request

from jarvis.agent import propose_only, check_only
from jarvis.calendar import list_events, find_conflicts
from jarvis.email import send_proposal
from jarvis.auth import get_calendar_service
from jarvis import store
from jarvis import config

app = Flask(__name__)

_lock = threading.Lock()
_log_q = queue.Queue()
_running = {"value": False}


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
            _log_q.put("\n[webui] a task is already running\n")
            return
        _running["value"] = True

    def worker():
        try:
            with redirect_stdout(_Tee(sys.stdout, _log_q)):
                fn()
        except Exception as e:
            _log_q.put(f"\n[webui] ERROR: {e!r}\n")
        finally:
            _log_q.put("\n[webui] --- task finished ---\n")
            _running["value"] = False

    threading.Thread(target=worker, daemon=True).start()


PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Jarvis — form demo</title>
  <style>
    :root { --bg:#0b0e14; --panel:#0f172a; --line:#1e293b; --text:#c8d0e0; --accent:#7dd3fc; --good:#4ade80; --bad:#f87171; --warn:#fbbf24; }
    body { font-family: ui-monospace, Menlo, Consolas, monospace; background:var(--bg); color:var(--text); margin:0; padding:24px; }
    h1 { color:var(--accent); margin:0 0 4px; font-size:20px; }
    .sub { color:#64748b; font-size:12px; margin-bottom:20px; }
    .grid { display:grid; grid-template-columns: 380px 1fr; gap:20px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }
    label { display:block; font-size:12px; color:#94a3b8; margin:12px 0 4px; }
    select, input { width:100%; background:#0b1220; color:var(--text); border:1px solid var(--line); padding:8px; border-radius:6px; font-family:inherit; font-size:13px; }
    button { background:#1e293b; color:#e2e8f0; border:1px solid #334155; padding:10px 14px; border-radius:6px; cursor:pointer; font-family:inherit; font-size:13px; }
    button:hover { background:#334155; }
    button:disabled { opacity:.4; cursor:not-allowed; }
    button.primary { background:#0369a1; border-color:#0284c7; }
    button.primary:hover { background:#0284c7; }
    .row { display:flex; gap:8px; margin-top:16px; flex-wrap:wrap; }
    pre { background:#0b1220; border:1px solid var(--line); border-radius:6px; padding:12px; min-height:280px; max-height:60vh; overflow:auto; white-space:pre-wrap; font-size:12px; line-height:1.45; }
    .status { font-size:12px; color:#64748b; margin-left:8px; }
    .event-card { border-left:3px solid var(--warn); padding:8px 12px; margin:8px 0; background:#0b1220; border-radius:4px; }
    .event-card .t { color:#e2e8f0; font-weight:600; }
    .event-card .m { color:#94a3b8; font-size:12px; }
    .pill { display:inline-block; padding:2px 8px; border-radius:99px; font-size:11px; margin-left:6px; }
    .pill.good { background:#064e3b; color:var(--good); }
    .pill.bad { background:#450a0a; color:var(--bad); }
    .pill.warn { background:#451a03; color:var(--warn); }
  </style>
</head>
<body>
  <h1>Jarvis — pick a conflict, pick a new time, confirm</h1>
  <div class="sub">Same pipeline as the CLI. Form just gives you a UI on top of <code>propose_specific()</code>.</div>

  <div class="grid">
    <div class="panel">
      <label>Step 1 — pick the conflict</label>
      <select id="conflict"></select>

      <label>Step 2 — pick a new start time</label>
      <input type="datetime-local" id="newStart">

      <div class="row">
        <button class="primary" onclick="sendProposal()" id="btn-send">Confirm &amp; Send proposal</button>
      </div>

      <label>Step 3 — simulate or check the reply</label>
      <select id="simulate">
        <option value="check">Read replies from Gmail (real)</option>
        <option value="accept">Simulate: accept</option>
        <option value="decline">Simulate: decline</option>
        <option value="unclear">Simulate: unclear</option>
      </select>
      <div class="row">
        <button onclick="runCheck()" id="btn-check">Run check</button>
        <button onclick="reset()" id="btn-reset">Reset demo state</button>
      </div>

      <div class="status" id="status">idle</div>
    </div>

    <div class="panel">
      <div id="events"></div>
      <pre id="log"></pre>
    </div>
  </div>

<script>
const $ = (id) => document.getElementById(id);
let conflicts = [];

async function loadState() {
  const r = await fetch('/api/state');
  const s = await r.json();
  conflicts = s.conflicts || [];
  $('conflict').innerHTML = conflicts.map((c, i) =>
    `<option value="${i}">[${c.a.summary}] ${c.a.start} vs [${c.b.summary}] ${c.b.start}</option>`
  ).join('') || '<option>no conflicts — run reset + seed</option>';

  const newStart = $('newStart');
  if (!newStart.value && conflicts.length) {
    newStart.value = conflicts[0].suggested_start.slice(0,16);
  }

  $('events').innerHTML =
    '<div class="sub">Current upcoming events</div>' +
    (s.events || []).map(e =>
      `<div class="event-card"><div class="t">${e.summary}</div><div class="m">${e.start} → ${e.end}  (${e.calendar})</div></div>`
    ).join('');
}

function append(s) {
  const el = $('log');
  el.textContent += s;
  el.scrollTop = el.scrollHeight;
}

function setRunning(on) {
  ['btn-send','btn-check','btn-reset'].forEach(id => $(id).disabled = on);
  $('status').textContent = on ? 'running…' : 'idle';
}

function stream() {
  const src = new EventSource('/events');
  src.onmessage = (e) => {
    if (e.data === '__END__') { src.close(); setRunning(false); loadState(); return; }
    append(e.data.replace(/\\\\n/g, '\\n'));
  };
  src.onerror = () => { src.close(); setRunning(false); };
}

async function sendProposal() {
  $('log').textContent = '';
  setRunning(true);
  const idx = parseInt($('conflict').value, 10);
  const body = { conflict_index: idx, new_start: $('newStart').value };
  await fetch('/api/propose', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(body)});
  stream();
}

async function runCheck() {
  $('log').textContent = '';
  setRunning(true);
  const mode = $('simulate').value;
  await fetch('/api/check', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({mode})});
  stream();
}

async function reset() {
  $('log').textContent = '';
  setRunning(true);
  await fetch('/api/reset', {method:'POST'});
  stream();
}

loadState();
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
    out_conflicts = []
    for a, b in conflicts:
        later_end = max(a["end"], b["end"])
        base = later_end + timedelta(minutes=15)
        minute = 0 if base.minute < 30 else 30
        suggested = base.replace(minute=minute, second=0, microsecond=0)
        if suggested < base:
            suggested += timedelta(minutes=30)
        out_conflicts.append({
            "a": {"summary": a["summary"], "start": a["start"].strftime("%a %d %b %H:%M"), "end": a["end"].strftime("%H:%M")},
            "b": {"summary": b["summary"], "start": b["start"].strftime("%a %d %b %H:%M"), "end": b["end"].strftime("%H:%M")},
            "suggested_start": suggested.strftime("%Y-%m-%dT%H:%M"),
        })
    return jsonify({
        "events": [{
            "summary": e["summary"],
            "start": e["start"].strftime("%a %H:%M"),
            "end": e["end"].strftime("%H:%M"),
            "calendar": e["calendar"],
        } for e in events],
        "conflicts": out_conflicts,
    })


@app.post("/api/propose")
def api_propose():
    data = request.get_json(force=True)
    idx = int(data.get("conflict_index", 0))
    new_start_iso = data.get("new_start")

    def task():
        events = list_events()
        conflicts = find_conflicts(events)
        if not conflicts:
            print("[webui] no conflicts to propose.")
            return
        idx_safe = max(0, min(idx, len(conflicts) - 1))
        a, b = conflicts[idx_safe]
        new_start = datetime.fromisoformat(new_start_iso)
        duration = a["end"] - a["start"]
        new_end = new_start + duration
        print(f"[webui] sending proposal for '{a['summary']}' -> {new_start:%a %d %b %H:%M}")
        msg_id = send_proposal(config.my_email(), a, new_start, new_end)
        store.add_pending({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
        })
        print(f"[webui] sent id={msg_id}")

    _run(task)
    return {"ok": True}


@app.post("/api/check")
def api_check():
    data = request.get_json(force=True)
    mode = data.get("mode", "check")

    def task():
        if mode == "check":
            check_only()
            return
        # simulated reply — fake the decision, still run the real action
        pending = store.pending_only()
        if not pending:
            print("[webui] no pending proposals to simulate against.")
            return
        from jarvis.parse import parse_reply
        fake = {"accept": "Yes", "decline": "No", "unclear": "maybe later"}[mode]
        for p in pending:
            new_start = datetime.fromisoformat(p["new_start_iso"])
            print(f"[webui] simulating reply '{fake}' for '{p['summary']}'")
            d = parse_reply(fake, reference_date=new_start)
            print(f"[webui]   parsed -> {d['decision']}")
            if d["decision"] == "accept":
                from jarvis.auth import get_calendar_service
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
                print(f"[webui] moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
            elif d["decision"] == "decline":
                store.mark_resolved(p["proposal_msg_id"], "declined")
                store.log_escalation({"event": p["summary"], "reason": "declined",
                                      "proposal_msg_id": p["proposal_msg_id"]})
            else:
                store.mark_resolved(p["proposal_msg_id"], "escalated")
                store.log_escalation({"event": p["summary"], "reason": "unclear",
                                      "raw": fake, "proposal_msg_id": p["proposal_msg_id"]})

    _run(task)
    return {"ok": True}


@app.post("/api/reset")
def api_reset():
    def task():
        import subprocess, sys as _s
        print("[webui] running reset_calendar.py")
        r = subprocess.run([_s.executable, "reset_calendar.py"], capture_output=True, text=True)
        print(r.stdout or "", end="")
        if r.stderr:
            print(r.stderr)
        print("[webui] running seed_calendar.py")
        r = subprocess.run([_s.executable, "seed_calendar.py"], capture_output=True, text=True)
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
    print("Jarvis form UI -> http://127.0.0.1:8001")
    app.run(host="127.0.0.1", port=8001, debug=False, threaded=True)
