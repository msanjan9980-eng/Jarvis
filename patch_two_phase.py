"""Patch jarvis/agent.py to add two-phase propose/check."""
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()

# 1) add a state file path helper (after the imports block)
marker = "from jarvis.parse import decide_from_replies, parse_reply\n"
if "PENDING_PATH" not in src:
    src = src.replace(
        marker,
        marker + "\nimport json\n\n"
        "PENDING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"pending.json\")\n"
    )

# 2) add propose_only and check_only functions before "def main():"
if "def propose_only(" not in src:
    new_funcs = '''
def _save_pending(entries):
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def _load_pending():
    if not os.path.exists(PENDING_PATH):
        return []
    with open(PENDING_PATH, encoding="utf-8") as f:
        return json.load(f)


def propose_only():
    """Phase 1: find conflicts, send proposals, save pending state."""
    _log("PHASE 1: propose")
    events = list_events()
    conflicts = find_conflicts(events)
    if not conflicts:
        _log("  no conflicts. nothing to propose.")
        return
    pending = []
    for a, b in conflicts:
        _log(f"  conflict: '{a['summary']}' vs '{b['summary']}'")
        new_start, new_end = propose_new_time(a, b)
        msg_id = send_proposal(MY_EMAIL, a, new_start, new_end)
        _log(f"  sent proposal id={msg_id} proposing {new_start:%a %d %b %H:%M}")
        pending.append({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
        })
    _save_pending(pending)
    _log(f"  saved {len(pending)} pending proposal(s) -> {PENDING_PATH}")
    print()
    print("PHASE 1 DONE. Now reply to the email(s), then run: python -m jarvis.agent check")


def check_only():
    """Phase 2: read replies, match to pending proposals, act."""
    _log("PHASE 2: check")
    pending = _load_pending()
    if not pending:
        _log("  no pending proposals. run 'propose' first.")
        return
    replies = list_replies()
    _log(f"  {len(replies)} marker message(s)")
    results = []
    for p in pending:
        new_start = datetime.fromisoformat(p["new_start_iso"])
        decision = decide_from_replies(replies, reference_date=new_start)
        d = decision["decision"]
        _log(f"  '{p['summary']}' -> {d}")
        if d == "accept":
            from jarvis.auth import get_calendar_service
            svc = get_calendar_service()
            ev = svc.events().get(calendarId=p["calendar_id"], eventId=p["event_id"]).execute()
            old_start = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
            old_end = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
            duration = old_end - old_start
            svc.events().patch(
                calendarId=p["calendar_id"],
                eventId=p["event_id"],
                body={
                    "start": {"dateTime": new_start.isoformat(), "timeZone": "Asia/Kolkata"},
                    "end":   {"dateTime": (new_start + duration).isoformat(), "timeZone": "Asia/Kolkata"},
                },
            ).execute()
            _log(f"    moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
            results.append({"event": p["summary"], "status": "rescheduled"})
        elif d == "decline":
            results.append({"event": p["summary"], "status": "declined"})
        elif d == "no_reply":
            results.append({"event": p["summary"], "status": "awaiting_reply"})
        elif d == "propose_time":
            results.append({"event": p["summary"], "status": "counter_proposed", "new_start": str(decision.get("new_start"))})
        else:
            results.append({"event": p["summary"], "status": "escalate", "raw": decision.get("raw", "")[:120]})
    print()
    print("RESULT:", {"status": "ok", "results": results})


'''
    src = src.replace("def main():", new_funcs + "def main():")

# 3) add subparsers for propose and check
if 'add_parser("propose"' not in src:
    src = src.replace(
        '    p_demo = sub.add_parser("demo", help="force a failure path")',
        '    sub.add_parser("propose", help="phase 1: send proposals")\n'
        '    sub.add_parser("check", help="phase 2: read replies and act")\n\n'
        '    p_demo = sub.add_parser("demo", help="force a failure path")'
    )
    src = src.replace(
        '    elif args.cmd == "demo":\n        demo(args.path)',
        '    elif args.cmd == "propose":\n        propose_only()\n'
        '    elif args.cmd == "check":\n        check_only()\n'
        '    elif args.cmd == "demo":\n        demo(args.path)'
    )

open(path, "w", encoding="utf-8").write(src)
print("patched jarvis/agent.py with propose/check")
