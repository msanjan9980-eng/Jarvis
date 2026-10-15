"""Fix infinite-recursion bug in site.py dashboard."""
path = r"C:\JARVIS 2.0\site.py"
src = open(path, encoding="utf-8").read()

old = """DASHBOARD_JS = \"\"\"
async function loadStats(){
  await window._loadStats_orig();
  try{
    const r = await fetch('/api/state'); const s = await r.json();
    const ev = (s.events||[]).map(e =>
      `<div class="ev"><div class="title">${e.summary}<span class="pill info">scheduled</span></div>
       <div class="time">${e.start} → ${e.end}</div><div class="cal">${e.calendar}</div></div>`
    ).join('') || '<div class="ev"><div class="title">No upcoming events</div></div>';
    document.getElementById('events').innerHTML = ev;
    const cf = (s.conflicts||[]).map(c =>
      `<div class="ev"><div class="title">${c.a.summary} ↔ ${c.b.summary}<span class="pill bad">overlap</span></div>
       <div class="time">${c.a.start} vs ${c.b.start}</div><div class="cal">suggested · ${c.suggested_human||'—'}</div></div>`
    ).join('') || '<div class="ev"><div class="title">No conflicts</div></div>';
    document.getElementById('conflicts').innerHTML = cf;
  }catch(e){}
}
window._loadStats_orig = loadStats;
\"\"\""""

new = '''DASHBOARD_JS = """
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
"""'''

if old in src:
    src = src.replace(old, new)
    open(path, "w", encoding="utf-8").write(src)
    print("fixed: DASHBOARD_JS recursion removed")
else:
    print("!!! pattern not found — paste this output back to me")
