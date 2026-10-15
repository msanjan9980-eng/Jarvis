"""Append LLM fallback to jarvis/parse.py."""
path = r"C:\JARVIS 2.0\jarvis\parse.py"
src = open(path, encoding="utf-8").read()

if "def llm_parse(" not in src:
    src += '''

import json as _json
import os as _os
import urllib.request as _urlreq


def llm_parse(body):
    """Fallback for unclear replies. Returns decision dict or None."""
    key = _os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content":
             "Parse replies to a meeting-reschedule proposal. "
             "Return strict JSON: {\\"decision\\": \\"accept\\"|\\"decline\\"|\\"propose_time\\"|\\"unclear\\", "
             "\\"new_start\\": null or ISO8601}."},
            {"role": "user", "content": (body or "")[:2000]},
        ],
        "temperature": 0,
    }
    req = _urlreq.Request(
        "https://api.openai.com/v1/chat/completions",
        data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with _urlreq.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]
        parsed = _json.loads(content)
        from datetime import datetime as _dt
        if parsed.get("decision") == "propose_time" and parsed.get("new_start"):
            parsed["new_start"] = _dt.fromisoformat(parsed["new_start"].replace("Z", "+00:00"))
        return parsed
    except Exception:
        return None
'''
    open(path, "w", encoding="utf-8").write(src)
    print("appended llm_parse to jarvis/parse.py")
else:
    print("parse.py already has llm_parse")
