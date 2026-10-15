"""Prune also drops pending entries whose event no longer exists, plus legacy entries
   without a status field that can't be acted on."""
path = r"C:\JARVIS 2.0\jarvis\store.py"
src = open(path, encoding="utf-8").read()

old = src[src.index("def prune_resolved("):] if "def prune_resolved(" in src else None
new_fn = '''

def prune_resolved(calendar_service):
    """Drop any entry whose event no longer exists, and legacy entries without status."""
    entries = load_pending()
    kept = []
    for e in entries:
        # Drop legacy entries with no status field
        if not e.get("status"):
            continue
        try:
            calendar_service.events().get(
                calendarId=e["calendar_id"], eventId=e["event_id"]
            ).execute()
            kept.append(e)
        except Exception:
            # event gone -> drop regardless of status
            continue
    if len(kept) > 30:
        kept = kept[-30:]
    save_pending(kept)
    return len(entries) - len(kept)
'''

if old:
    src = src[:src.index("def prune_resolved(")] + new_fn.lstrip("\n")
    open(path, "w", encoding="utf-8").write(src)
    print("rewrote prune_resolved")
else:
    print("no prune_resolved found")
