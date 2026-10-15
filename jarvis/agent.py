"""Jarvis agent: detect conflicts, propose, parse reply, act, escalate.

CLI:
  python -m jarvis.agent run                   # handle first conflict
  python -m jarvis.agent run --all             # handle every conflict
  python -m jarvis.agent run --dry             # no writes, no emails
  python -m jarvis.agent demo --path <p>       # force failure path for demo
                                               # p in {accept,decline,unclear,no_reply,counter}
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

from jarvis.calendar import list_events, find_conflicts, pick_recipient
from jarvis.email import send_proposal, list_replies, list_replies_for_thread, send_confirmation
from jarvis.parse import decide_from_replies, parse_reply
from jarvis import store
from jarvis import config

import json

PENDING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending.json")

MY_EMAIL = config.my_email()


LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "jarvis.log"),
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)


def _log(msg):
    print(f"[jarvis] {msg}", flush=True)
    logging.info(msg)


def propose_new_time(conflict_a, conflict_b):
    later_end = max(conflict_a["end"], conflict_b["end"])
    base = later_end + timedelta(minutes=15)
    minute = 0 if base.minute < 30 else 30
    start = base.replace(minute=minute, second=0, microsecond=0)
    if start < base:
        start += timedelta(minutes=30)
    end = start + (conflict_a["end"] - conflict_a["start"])
    return start, end


def _move_event(a, new_start, dry=False):
    duration = a["end"] - a["start"]
    new_end = new_start + duration
    if dry:
        _log(f"  [dry] would move '{a['summary']}' to {new_start:%a %d %b %H:%M}")
        return
    from jarvis.auth import get_calendar_service
    svc = get_calendar_service()
    updated = svc.events().patch(
        calendarId=a["calendar_id"],
        eventId=a["id"],
        body={
            "start": {"dateTime": new_start.isoformat(), "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": new_end.isoformat(), "timeZone": "Asia/Kolkata"},
        },
    ).execute()
    _log(f"  moved '{updated.get('summary')}' to {new_start:%a %d %b %H:%M}")


def handle_one_conflict(a, b, dry=False, decision_override=None):
    """Returns a status dict for one conflict."""
    _log(f"  conflict: '{a['summary']}' vs '{b['summary']}'")
    new_start, new_end = propose_new_time(a, b)
    _log(f"  proposing {new_start:%a %d %b %H:%M}-{new_end:%H:%M}")

    if not dry:
        msg_id = send_proposal(MY_EMAIL, a, new_start, new_end)
        _log(f"  sent proposal id={msg_id}")
    else:
        _log("  [dry] would send proposal email")

    if decision_override is not None:
        decision = decision_override
        _log(f"  [demo] forced decision: {decision['decision']}")
    else:
        replies = list_replies()
        _log(f"  {len(replies)} marker message(s)")
        decision = decide_from_replies(replies, reference_date=new_start)

    d = decision["decision"]
    _log(f"  decision: {d}")

    if d == "accept":
        _move_event(a, new_start, dry=dry)
        return {"status": "rescheduled", "event": a["summary"], "new_start": new_start}
    if d == "propose_time":
        return {"status": "counter_proposed", "new_start": decision.get("new_start")}
    if d == "decline":
        return {"status": "declined", "event": a["summary"]}
    if d == "no_reply":
        return {"status": "awaiting_reply", "event": a["summary"]}
    return {"status": "escalate", "raw": decision.get("raw", "")[:120]}


def run(all_conflicts=False, dry=False):
    _log("Step 1: reading calendars...")
    events = list_events()
    _log(f"  {len(events)} timed events in next 7 days")

    _log("Step 2: detecting conflicts...")
    conflicts = find_conflicts(events)
    if not conflicts:
        _log("  no conflicts found. nothing to do.")
        return {"status": "no_conflicts", "results": []}

    _log(f"  {len(conflicts)} conflict(s) found")
    targets = conflicts if all_conflicts else conflicts[:1]

    results = []
    for i, (a, b) in enumerate(targets, 1):
        _log(f"--- Conflict {i}/{len(targets)} ---")
        results.append(handle_one_conflict(a, b, dry=dry))

    _log("Done.")
    return {"status": "ok", "results": results}


DEMO_PATHS = {
    "accept":     {"decision": "accept",        "raw": "Yes"},
    "decline":    {"decision": "decline",       "raw": "No"},
    "unclear":    {"decision": "unclear",       "raw": "maybe later, we should discuss"},
    "no_reply":   {"decision": "no_reply"},
    "counter":    {"decision": "propose_time",  "new_start": datetime.now() + timedelta(days=1, hours=6)},
}


def demo(path):
    if path not in DEMO_PATHS:
        print(f"unknown demo path: {path}. choose from: {list(DEMO_PATHS)}")
        sys.exit(2)
    _log(f"DEMO MODE: forcing '{path}' path (no Gmail read/write)")
    events = list_events()
    conflicts = find_conflicts(events)
    if not conflicts:
        _log("no conflicts to demo. run seed_calendar.py first.")
        return
    a, b = conflicts[0]
    result = handle_one_conflict(a, b, dry=True, decision_override=DEMO_PATHS[path])
    print()
    print("RESULT:", result)



def _save_pending(entries):
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def _load_pending():
    if not os.path.exists(PENDING_PATH):
        return []
    with open(PENDING_PATH, encoding="utf-8") as f:
        return json.load(f)




def _has_pending_proposal(event_id):
    """True if a proposal for this event is still awaiting a reply."""
    for p in store.pending_only():
        if p.get("event_id") == event_id:
            return True
    return False


def propose_only():
    """Phase 1: find conflicts, send proposals, save pending state."""
    _log("PHASE 1: propose")
    from jarvis.auth import get_calendar_service
    _dropped = store.prune_resolved(get_calendar_service())
    if _dropped:
        _log(f"  pruned {_dropped} stale resolved entr(ies)")
    events = list_events()
    conflicts = find_conflicts(events)
    if not conflicts:
        _log("  no conflicts. nothing to propose.")
        return
    pending = []
    for a, b in conflicts:
        _log(f"  conflict: '{a['summary']}' vs '{b['summary']}'")
        if _has_pending_proposal(a["id"]):
            _log(f"  skip: a proposal for '{a['summary']}' is already pending")
            continue
        new_start, new_end = propose_new_time(a, b)
        recipient = pick_recipient(a, MY_EMAIL)
        if recipient == MY_EMAIL:
            _log(f"  recipient: (no other attendees) {recipient}")
        else:
            _log(f"  recipient: {recipient} (from attendees)")
        msg_id = send_proposal(recipient, a, new_start, new_end)
        _log(f"  sent proposal id={msg_id} proposing {new_start:%a %d %b %H:%M}")
        store.add_pending({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
            "recipient": recipient,
        })
    _log(f"  saved {len(conflicts)} pending proposal(s)")
    print()
    print("PHASE 1 DONE. Now reply to the email(s), then run: python -m jarvis.agent check")


def check_only():
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
            try:
                _tmp_ev = _get_event(p["calendar_id"], p["event_id"])
                dur = datetime.fromisoformat(_tmp_ev["end"]["dateTime"].replace("Z","+00:00")) - \
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
    try:
        recipient = p.get("recipient") or MY_EMAIL
        send_confirmation(recipient, p["summary"], new_start, new_start + dur,
                          in_reply_to_msg_id=p.get("proposal_msg_id"))
        _log(f"    sent confirmation to {recipient}")
    except Exception as e:
        _log(f"    confirmation send failed: {e!r}")




def watch(interval=60, cycles=None):
    """Run propose + check in a loop. Ctrl+C to stop."""
    import time
    n = 0
    try:
        while cycles is None or n < cycles:
            n += 1
            _log(f"=== WATCH CYCLE {n} ===")
            try:
                propose_only()
            except Exception as e:
                _log(f"  propose failed: {e!r}")
            try:
                check_only()
            except Exception as e:
                _log(f"  check failed: {e!r}")
            if cycles is not None and n >= cycles:
                break
            _log(f"  sleeping {interval}s (Ctrl+C to stop)...")
            time.sleep(interval)
    except KeyboardInterrupt:
        _log("watch stopped by user")


def main():
    parser = argparse.ArgumentParser(prog="jarvis.agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="normal pipeline")
    p_run.add_argument("--all", action="store_true", help="handle every conflict")
    p_run.add_argument("--dry", action="store_true", help="no writes, no emails")

    sub.add_parser("propose", help="phase 1: send proposals")
    sub.add_parser("check", help="phase 2: read replies and act")

    sub.add_parser("escalations", help="list logged escalations")

    p_watch = sub.add_parser("watch", help="run propose+check on a loop")
    p_watch.add_argument("--interval", type=int, default=60, help="seconds between cycles")
    p_watch.add_argument("--cycles", type=int, default=None, help="stop after N cycles")

    p_demo = sub.add_parser("demo", help="force a failure path")
    p_demo.add_argument("--path", required=True, choices=list(DEMO_PATHS))

    args = parser.parse_args()
    if args.cmd == "run":
        result = run(all_conflicts=args.all, dry=args.dry)
        print()
        print("RESULT:", result)
    elif args.cmd == "propose":
        propose_only()
    elif args.cmd == "check":
        check_only()
    elif args.cmd == "escalations":
        import json as _j
        print(_j.dumps(store.list_escalations(), indent=2, default=str))
    elif args.cmd == "watch":
        watch(interval=args.interval, cycles=args.cycles)
    elif args.cmd == "demo":
        demo(args.path)


if __name__ == "__main__":
    main()
