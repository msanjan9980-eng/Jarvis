"""Keep pending.json bounded: on propose, prune resolved entries
   whose event no longer exists on the calendar, and cap total size."""
path = r"C:\JARVIS 2.0\jarvis\store.py"
src = open(path, encoding="utf-8").read()

if "def prune_resolved(" not in src:
    add = '''

def prune_resolved(calendar_service):
    """Drop resolved entries whose underlying event no longer exists.
       Keeps pending + recently-resolved entries."""
    entries = load_pending()
    kept = []
    for e in entries:
        if e.get("status") == "pending":
            kept.append(e)
            continue
        # resolved: check if event still exists
        try:
            calendar_service.events().get(
                calendarId=e["calendar_id"], eventId=e["event_id"]
            ).execute()
            kept.append(e)
        except Exception:
            # event gone; drop this entry
            pass
    # hard cap: keep only the last 30 entries
    if len(kept) > 30:
        kept = kept[-30:]
    save_pending(kept)
    return len(entries) - len(kept)
'''
    src = src + add
    open(path, "w", encoding="utf-8").write(src)
    print("patched jarvis/store.py with prune_resolved")
else:
    print("store.py already patched")

# Wire prune into propose_only
apath = r"C:\JARVIS 2.0\jarvis\agent.py"
asrc = open(apath, encoding="utf-8").read()
if "prune_resolved" not in asrc:
    asrc = asrc.replace(
        '    _log("PHASE 1: propose")\n    events = list_events()',
        '    _log("PHASE 1: propose")\n    from jarvis.auth import get_calendar_service\n'
        '    _dropped = store.prune_resolved(get_calendar_service())\n'
        '    if _dropped:\n        _log(f"  pruned {_dropped} stale resolved entr(ies)")\n'
        '    events = list_events()'
    )
    open(apath, "w", encoding="utf-8").write(asrc)
    print("patched jarvis/agent.py to prune on propose")
else:
    print("agent.py already patched")
