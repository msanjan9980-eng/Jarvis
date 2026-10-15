"""Jarvis — add-event form. Port 8003. Standalone.

Creates real Google Calendar events. Existing UIs untouched.
"""
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request
from jarvis.auth import get_calendar_service

app = Flask(__name__)

PAGE = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Add event · Jarvis</title>
<style>
  :root { --bg:#05070d; --panel:#0f172a; --line:#1e2a44; --txt:#e6ecf7; --dim:#94a3b8; --acc:#38bdf8; --ok:#22c55e; --bad:#ef4444; }
  body { margin:0; background:radial-gradient(1200px 600px at 15% -10%, #0c1830, #05070d) fixed; color:var(--txt); font-family:'Inter',system-ui,sans-serif; }
  .wrap { max-width:640px; margin:0 auto; padding:48px 24px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--dim); font-size:13px; margin-bottom:28px; }
  label { display:block; font-size:11px; text-transform:uppercase; letter-spacing:1.2px; color:var(--dim); margin:18px 0 6px; }
  input, select { width:100%; background:#0b1220; border:1px solid var(--line); color:var(--txt); padding:11px 13px; border-radius:8px; font-family:inherit; font-size:14px; }
  input:focus, select:focus { outline:none; border-color:var(--acc); box-shadow:0 0 0 3px rgba(56,189,248,.15); }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  button { margin-top:26px; width:100%; padding:13px; background:linear-gradient(180deg,#0ea5e9,#0369a1); border:1px solid #0284c7; color:#001; font-weight:700; border-radius:8px; cursor:pointer; font-size:14px; }
  button:hover { filter:brightness(1.1); }
  button:disabled { opacity:.4; cursor:not-allowed; }
  .result { margin-top:20px; padding:14px 16px; border-radius:8px; font-size:13px; display:none; }
  .result.ok { display:block; background:rgba(34,197,94,.12); border:1px solid #166534; color:#86efac; }
  .result.bad { display:block; background:rgba(239,68,68,.12); border:1px solid #7f1d1d; color:#fca5a5; }
  .hint { margin-top:14px; font-size:11px; color:var(--dim); line-height:1.6; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Add a calendar event</h1>
  <div class="sub">Writes to your primary Google Calendar. It'll be picked up by the agent on next run.</div>

  <label>Event title</label>
  <input id="summary" placeholder="e.g. Client call" autofocus>

  <div class="row">
    <div>
      <label>Date</label>
      <input type="date" id="date">
    </div>
    <div>
      <label>Start time</label>
      <input type="time" id="start" value="10:00">
    </div>
  </div>

  <label>Duration (minutes)</label>
  <select id="duration">
    <option>15</option><option>30</option><option selected>45</option>
    <option>60</option><option>90</option><option>120</option>
  </select>

  <label>Add guest (optional, comma-separated emails)</label>
  <input id="attendees" placeholder="priya@example.com, sam@example.com">

  <button id="go" onclick="submit()">Create event</button>
  <div class="result" id="result"></div>
  <div class="hint">Timezone: Asia/Kolkata. Created on the primary calendar of the signed-in account.</div>
</div>

<script>
const $ = (id) => document.getElementById(id);
function setResult(kind, msg) {
  const r = $('result');
  r.className = 'result ' + kind;
  r.textContent = msg;
}
async function submit() {
  const body = {
    summary: $('summary').value.trim(),
    date: $('date').value,
    start: $('start').value,
    duration: parseInt($('duration').value, 10),
    attendees: $('attendees').value.split(',').map(s => s.trim()).filter(Boolean),
  };
  if (!body.summary || !body.date || !body.start) {
    setResult('bad', 'Please fill in title, date, and start time.');
    return;
  }
  $('go').disabled = true;
  setResult('ok', 'Creating…');
  try {
    const r = await fetch('/api/add', {
      method:'POST',
      headers:{'content-type':'application/json'},
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (j.ok) {
      setResult('ok', 'Created: ' + j.summary + ' on ' + j.start);
      $('summary').value = '';
      $('attendees').value = '';
    } else {
      setResult('bad', 'Error: ' + j.error);
    }
  } catch (e) {
    setResult('bad', 'Error: ' + e.message);
  }
  $('go').disabled = false;
}
// prefill date = tomorrow
const t = new Date(); t.setDate(t.getDate() + 1);
$('date').value = t.toISOString().slice(0,10);
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/api/add")
def api_add():
    data = request.get_json(force=True)
    try:
        summary = data["summary"].strip()
        date_str = data["date"]           # YYYY-MM-DD
        start_str = data["start"]         # HH:MM
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
        return jsonify({
            "ok": True,
            "id": created["id"],
            "summary": created.get("summary", summary),
            "start": start.strftime("%a %d %b %H:%M"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": repr(e)})


if __name__ == "__main__":
    print("Add-event UI -> http://127.0.0.1:8003")
    app.run(host="127.0.0.1", port=8003, debug=False, threaded=True)
