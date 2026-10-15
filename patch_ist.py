"""Force IST display in jarvis/calendar.py. Safe: all datetimes stay aware."""
path = r"C:\JARVIS 2.0\jarvis\calendar.py"
src = open(path, encoding="utf-8").read()
changed = []

# 1) ensure ZoneInfo import + IST constant at top
if "from zoneinfo import ZoneInfo" not in src:
    src = src.replace(
        "from datetime import datetime, timedelta",
        "from datetime import datetime, timedelta\nfrom zoneinfo import ZoneInfo\n\nIST = ZoneInfo(\"Asia/Kolkata\")"
    )
    changed.append("import ZoneInfo + IST")

# 2) force _parse to return IST-aware datetimes
old = '    s = dt_str.replace("Z", "+00:00")\n    return datetime.fromisoformat(s)'
new = '    s = dt_str.replace("Z", "+00:00")\n    return datetime.fromisoformat(s).astimezone(IST)'
if old in src:
    src = src.replace(old, new)
    changed.append("_parse -> IST")
else:
    print("!!! _parse pattern not found — check the file")

open(path, "w", encoding="utf-8").write(src)
print("calendar.py:", ", ".join(changed) if changed else "already patched")
