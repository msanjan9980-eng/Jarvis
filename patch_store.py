"""Wire agent.py to jarvis.store: persist pending, resolve on action, log escalations."""
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()

# 1) Replace the local _save_pending / _load_pending with store calls
if "from jarvis import store" not in src:
    src = src.replace(
        "from jarvis.parse import decide_from_replies, parse_reply",
        "from jarvis.parse import decide_from_replies, parse_reply\nfrom jarvis import store"
    )

# 2) propose_only: use store.add_pending
src = src.replace(
    """        pending.append({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
        })
    _save_pending(pending)
    _log(f"  saved {len(pending)} pending proposal(s) -> {PENDING_PATH}")""",
    """        store.add_pending({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
        })
    _log(f"  saved {len(targets)} pending proposal(s)")"""
)

# 3) check_only: only load pending, mark resolved, log escalations
src = src.replace(
    """    pending = _load_pending()
    if not pending:
        _log("  no pending proposals. run 'propose' first.")
        return""",
    """    pending = store.pending_only()
    if not pending:
        _log("  no pending proposals. run 'propose' first.")
        return"""
)

# 4) after each decision, resolve or escalate
src = src.replace(
    """            _log(f"    moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
            results.append({"event": p["summary"], "status": "rescheduled"})
        elif d == "decline":
            results.append({"event": p["summary"], "status": "declined"})
        elif d == "no_reply":
            results.append({"event": p["summary"], "status": "awaiting_reply"})
        elif d == "propose_time":
            results.append({"event": p["summary"], "status": "counter_proposed", "new_start": str(decision.get("new_start"))})
        else:
            results.append({"event": p["summary"], "status": "escalate", "raw": decision.get("raw", "")[:120]})""",
    """            _log(f"    moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
            store.mark_resolved(p["proposal_msg_id"], "rescheduled")
            results.append({"event": p["summary"], "status": "rescheduled"})
        elif d == "decline":
            store.mark_resolved(p["proposal_msg_id"], "declined")
            store.log_escalation({"event": p["summary"], "reason": "declined",
                                  "proposal_msg_id": p["proposal_msg_id"]})
            results.append({"event": p["summary"], "status": "declined"})
        elif d == "no_reply":
            results.append({"event": p["summary"], "status": "awaiting_reply"})
        elif d == "propose_time":
            store.mark_resolved(p["proposal_msg_id"], "counter_proposed")
            store.log_escalation({"event": p["summary"], "reason": "counter_proposed",
                                  "new_start": str(decision.get("new_start")),
                                  "proposal_msg_id": p["proposal_msg_id"]})
            results.append({"event": p["summary"], "status": "counter_proposed", "new_start": str(decision.get("new_start"))})
        else:
            store.mark_resolved(p["proposal_msg_id"], "escalated")
            store.log_escalation({"event": p["summary"], "reason": "unclear",
                                  "raw": decision.get("raw", "")[:200],
                                  "proposal_msg_id": p["proposal_msg_id"]})
            results.append({"event": p["summary"], "status": "escalate", "raw": decision.get("raw", "")[:120]})"""
)

# 5) add `escalations` subcommand
if 'add_parser("escalations"' not in src:
    src = src.replace(
        '    p_demo = sub.add_parser("demo", help="force a failure path")',
        '    sub.add_parser("escalations", help="list logged escalations")\n\n'
        '    p_demo = sub.add_parser("demo", help="force a failure path")'
    )
    src = src.replace(
        '    elif args.cmd == "demo":\n        demo(args.path)',
        '    elif args.cmd == "escalations":\n        import json as _j\n        print(_j.dumps(store.list_escalations(), indent=2, default=str))\n'
        '    elif args.cmd == "demo":\n        demo(args.path)'
    )

open(path, "w", encoding="utf-8").write(src)
print("patched agent.py with store integration")
