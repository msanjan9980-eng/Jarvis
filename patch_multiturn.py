"""Add round-1/round-2 multi-turn negotiation to check_only."""

# --- store.py: add a round-aware helper ---
spath = r"C:\JARVIS 2.0\jarvis\store.py"
ssrc = open(spath, encoding="utf-8").read()

if "def add_counter_proposal(" not in ssrc:
    ssrc += '''

def add_counter_proposal(original_pending, new_start, new_msg_id, reference):
    """When a user counters with a new time, create a round-2 pending entry.
    Marks the original entry as counter_proposed so it isn't reprocessed."""
    mark_resolved(original_pending["proposal_msg_id"], "counter_proposed")
    entries = load_pending()
    entries.append({
        "event_id": original_pending["event_id"],
        "calendar_id": original_pending["calendar_id"],
        "summary": original_pending["summary"],
        "new_start_iso": new_start.isoformat(),
        "proposal_msg_id": new_msg_id,
        "round": 2,
        "counter_of": original_pending["proposal_msg_id"],
        "created_at": _now(),
        "status": "pending",
    })
    save_pending(entries)
'''
    open(spath, "w", encoding="utf-8").write(ssrc)
    print("patched jarvis/store.py (add_counter_proposal)")
else:
    print("store.py already patched")

# --- agent.py: replace check_only with a round-aware version ---
apath = r"C:\JARVIS 2.0\jarvis\agent.py"
asrc = open(apath, encoding="utf-8").read()

# replace check_only entirely (from "def check_only(" to just before "def main(")
start = asrc.index("def check_only(")
end = asrc.index("def main(")
new_check = '''def check_only():
    """Phase 2: read replies, match to pending proposals, act.

    Round-aware: a round-1 counter-offer creates a round-2 pending entry.
    A round-2 counter-offer escalates (no further rounds).
    """
    _log("PHASE 2: check")
    pending = store.pending_only()
    if not pending:
        _log("  no pending proposals. run 'propose' first.")
        return
    from jarvis.email import list_replies_for_thread
    results = []
    for p in pending:
        replies = list_replies_for_thread(p["proposal_msg_id"])
        new_start = datetime.fromisoformat(p["new_start_iso"])
        decision = decide_from_replies(replies, reference_date=new_start)
        d = decision["decision"]
        round_no = p.get("round", 1)
        _log(f"  '{p['summary']}' [round {round_no}] -> {d}")

        if d == "accept":
            _do_move(p, new_start)
            store.mark_resolved(p["proposal_msg_id"], "rescheduled")
            results.append({"event": p["summary"], "status": "rescheduled", "round": round_no})
            continue

        if d == "decline":
            store.mark_resolved(p["proposal_msg_id"], "declined")
            store.log_escalation({"event": p["summary"], "reason": "declined",
                                  "proposal_msg_id": p["proposal_msg_id"]})
            results.append({"event": p["summary"], "status": "declined", "round": round_no})
            continue

        if d == "propose_time":
            counter = decision.get("new_start")
            if round_no >= 2:
                _log(f"    round 2 counter received ({counter}) -> escalating (no further rounds)")
                store.mark_resolved(p["proposal_msg_id"], "escalated")
                store.log_escalation({"event": p["summary"], "reason": "counter_at_round_2",
                                      "proposed": str(counter),
                                      "proposal_msg_id": p["proposal_msg_id"]})
                results.append({"event": p["summary"], "status": "escalate",
                                "raw": f"counter at round 2: {counter}"})
                continue
            _log(f"    round 1 counter received ({counter}) -> sending follow-up proposal")
            new_end = counter + (datetime.fromisoformat(p["new_start_iso"]) -
                                 datetime.fromisoformat(p["new_start_iso"])) + (new_start and __import__("datetime").timedelta(minutes=30) - __import__("datetime").timedelta(minutes=30))
            # simpler: keep 30 min default if we can't compute duration
            try:
                _tmp_ev = _get_event(p["calendar_id"], p["event_id"])
                dur = datetime.fromisoformat(_tmp_ev["end"]["dateTime"].replace("Z","+00:00")) - \\
                      datetime.fromisoformat(_tmp_ev["start"]["dateTime"].replace("Z","+00:00"))
            except Exception:
                dur = __import__("datetime").timedelta(minutes=30)
            new_end = counter + dur
            msg_id = send_proposal(MY_EMAIL, {"summary": p["summary"],
                                              "start": datetime.fromisoformat(p["new_start_iso"]),
                                              "end": datetime.fromisoformat(p["new_start_iso"]) + dur},
                                   counter, new_end)
            _log(f"    sent follow-up proposal id={msg_id} for {counter:%a %d %b %H:%M}")
            store.add_counter_proposal(p, counter, msg_id, reference=counter)
            results.append({"event": p["summary"], "status": "counter_proposed",
                            "new_start": str(counter), "round": round_no})
            continue

        if d == "no_reply":
            results.append({"event": p["summary"], "status": "awaiting_reply", "round": round_no})
            continue

        store.mark_resolved(p["proposal_msg_id"], "escalated")
        store.log_escalation({"event": p["summary"], "reason": "unclear",
                              "raw": decision.get("raw", "")[:200],
                              "proposal_msg_id": p["proposal_msg_id"]})
        results.append({"event": p["summary"], "status": "escalate",
                        "raw": decision.get("raw", "")[:120], "round": round_no})
    print()
    print("RESULT:", {"status": "ok", "results": results})


def _get_event(calendar_id, event_id):
    from jarvis.auth import get_calendar_service
    return get_calendar_service().events().get(calendarId=calendar_id, eventId=event_id).execute()


def _do_move(p, new_start):
    from jarvis.auth import get_calendar_service
    svc = get_calendar_service()
    ev = svc.events().get(calendarId=p["calendar_id"], eventId=p["event_id"]).execute()
    old_start = datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
    old_end = datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
    dur = old_end - old_start
    svc.events().patch(
        calendarId=p["calendar_id"], eventId=p["event_id"],
        body={"start": {"dateTime": new_start.isoformat(), "timeZone": "Asia/Kolkata"},
              "end": {"dateTime": (new_start + dur).isoformat(), "timeZone": "Asia/Kolkata"}},
    ).execute()
    _log(f"    moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")


'''
asrc = asrc[:start] + new_check + asrc[end:]
open(apath, "w", encoding="utf-8").write(asrc)
print("patched jarvis/agent.py (round-aware check_only)")
