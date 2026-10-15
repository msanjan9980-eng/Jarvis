"""Clear pending.json and escalations.json when resetting the calendar."""
path = r"C:\JARVIS 2.0\reset_calendar.py"
src = open(path, encoding="utf-8").read()

if "pending.json" not in src:
    src += '''

# Clear stored state so we start from a clean slate
import os
base = os.path.dirname(os.path.abspath(__file__))
for fname in ("pending.json", "escalations.json"):
    p = os.path.join(base, "jarvis", fname)
    if os.path.exists(p):
        os.remove(p)
        print(f"cleared: jarvis/{fname}")
'''
    open(path, "w", encoding="utf-8").write(src)
    print("patched reset_calendar.py")
else:
    print("reset_calendar.py already patched")
