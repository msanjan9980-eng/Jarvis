"""Thin web UI for Jarvis. Runs existing agent functions, streams their output.

No changes to the pipeline. If this file breaks, the CLI still works.
"""
import io
import queue
import sys
import threading
from contextlib import redirect_stdout

from flask import Flask, Response, render_template_string, request

from jarvis.agent import propose_only, check_only
from jarvis import store

app = Flask(__name__)

# One global event log per running task (fine for a hackathon demo).
_lock = threading.Lock()
_current_log = queue.Queue()
_task_running = {"value": False}


class _Tee(io.TextIOBase):
    """Write to both the original stdout and a queue (for SSE streaming)."""
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


def _run_task(fn):
    """Run fn() in a background thread, teeing stdout to the SSE queue."""
    with _lock:
        if _task_running["value"]:
            _current_log.put("\n[webui] a task is already running\n")
            return
        _task_running["value"] = True

    def worker():
        try:
            tee = _Tee(sys.stdout, _current_log)
            with redirect_stdout(tee):
                fn()
        except Exception as e:
            _current_log.put(f"\n[webui] ERROR: {e!r}\n")
        finally:
            _current_log.put("\n[webui] --- task finished ---\n")
            _task_running["value"] = False

    threading.Thread(target=worker, daemon=True).start()


PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Jarvis</title>
  <style>
    body { font-family: ui-monospace, Menlo, Consolas, monospace; background:#0b0e14; color:#c8d0e0; margin:0; padding:24px; }
    h1 { color:#7dd3fc; margin:0 0 12px; font-size:20px; }
    .row { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
    button { background:#1e293b; color:#e2e8f0; border:1px solid #334155; padding:10px 14px; border-radius:6px; cursor:pointer; font-family:inherit; font-size:14px; }
    button:hover { background:#334155; }
    button:disabled { opacity:.4; cursor:not-allowed; }
    pre { background:#0f172a; border:1px solid #1e293b; padding:14px; border-radius:8px; min-height:400px; max-height:70vh; overflow:auto; white-space:pre-wrap; font-size:13px; line-height:1.4; }
    .status { color:#64748b; font-size:12px; margin-left:8px; }
  </style>
</head>
<body>
  <h1>Jarvis — meeting conflict resolver</h1>
  <div class="row">
    <button onclick="run('propose')" id="btn-propose">1. Propose (send emails)</button>
    <button onclick="run('check')" id="btn-check">2. Check replies (act)</button>
    <button onclick="clearLog()">Clear</button>
    <span class="status" id="status">idle</span>
  </div>
  <pre id="log"></pre>

<script>
const logEl = document.getElementById('log');
const statusEl = document.getElementById('status');
const btnP = document.getElementById('btn-propose');
const btnC = document.getElementById('btn-check');

function setRunning(on) {
  btnP.disabled = on;
  btnC.disabled = on;
  statusEl.textContent = on ? 'running...' : 'idle';
}

function clearLog() { logEl.textContent = ''; }

function append(s) {
  logEl.textContent += s;
  logEl.scrollTop = logEl.scrollHeight;
}

function run(action) {
  clearLog();
  setRunning(true);
  fetch('/run/' + action, {method:'POST'});
  const src = new EventSource('/events');
  src.onmessage = (e) => {
    if (e.data === '__END__') { src.close(); setRunning(false); return; }
    append(e.data.replace(/\\\\n/g, '\\n'));
  };
  src.onerror = () => { src.close(); setRunning(false); };
}

// Auto-close the SSE stream after the server says the task finished.
window.addEventListener('beforeunload', () => {});
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/run/propose")
def run_propose():
    _run_task(propose_only)
    return {"ok": True}


@app.post("/run/check")
def run_check():
    _run_task(check_only)
    return {"ok": True}


@app.get("/events")
def events():
    """Server-sent events: stream whatever the worker is writing to stdout."""
    def gen():
        idle_ticks = 0
        while True:
            try:
                chunk = _current_log.get(timeout=0.5)
                idle_ticks = 0
                # escape newlines so each SSE message stays one line
                yield f"data: {chunk.replace(chr(10), '\\\\n')}\n\n"
                if "task finished" in chunk:
                    yield "data: __END__\n\n"
                    return
            except queue.Empty:
                idle_ticks += 1
                yield ": keepalive\n\n"
                if idle_ticks > 240:  # ~2 min safety cap
                    yield "data: __END__\n\n"
                    return
    return Response(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("Jarvis web UI -> http://127.0.0.1:8000")
    app.run(host="127.0.0.1", port=8000, debug=False, threaded=True)
