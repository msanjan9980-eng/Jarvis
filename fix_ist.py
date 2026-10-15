"""Replace ZoneInfo with fixed-offset IST. No tzdata needed on Windows."""
path = r"C:\JARVIS 2.0\jarvis\calendar.py"
src = open(path, encoding="utf-8").read()

old = 'from zoneinfo import ZoneInfo\n\nIST = ZoneInfo("Asia/Kolkata")'
new = 'from datetime import timezone as _tz\n\nIST = _tz(timedelta(hours=5, minutes=30))  # Asia/Kolkata, no DST'

if old in src:
    src = src.replace(old, new)
    open(path, "w", encoding="utf-8").write(src)
    print("fixed: ZoneInfo -> fixed-offset IST")
else:
    print("pattern not found — check file")
