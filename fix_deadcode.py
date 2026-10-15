"""Remove the dead-code line in check_only."""
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()

bad = """            _log(f"    round 1 counter received ({counter}) -> sending follow-up proposal")
            new_end = counter + (datetime.fromisoformat(p["new_start_iso"]) -
                                 datetime.fromisoformat(p["new_start_iso"])) + (new_start and __import__("datetime").timedelta(minutes=30) - __import__("datetime").timedelta(minutes=30))
            # simpler: keep 30 min default if we can't compute duration
"""
good = """            _log(f"    round 1 counter received ({counter}) -> sending follow-up proposal")
"""

if bad in src:
    src = src.replace(bad, good)
    open(path, "w", encoding="utf-8").write(src)
    print("removed dead-code line")
else:
    print("pattern not found — check the file manually")
