"""Persistent state for pending proposals + escalation log."""
import json
import os
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
PENDING_PATH = os.path.join(BASE, "pending.json")
ESCALATIONS_PATH = os.path.join(BASE, "escalations.json")


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_pending():
    if not os.path.exists(PENDING_PATH):
        return []
    with open(PENDING_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_pending(entries):
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def add_pending(entry):
    entries = load_pending()
    entry.setdefault("created_at", _now())
    entry.setdefault("status", "pending")
    entries.append(entry)
    save_pending(entries)
    return entry


def mark_resolved(proposal_msg_id, status, note=None):
    entries = load_pending()
    for e in entries:
        if e.get("proposal_msg_id") == proposal_msg_id and e.get("status") == "pending":
            e["status"] = status
            e["resolved_at"] = _now()
            if note:
                e["note"] = note
    save_pending(entries)


def pending_only():
    return [e for e in load_pending() if e.get("status") == "pending"]


def log_escalation(entry):
    log = []
    if os.path.exists(ESCALATIONS_PATH):
        with open(ESCALATIONS_PATH, encoding="utf-8") as f:
            log = json.load(f)
    entry["logged_at"] = _now()
    log.append(entry)
    with open(ESCALATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, default=str)
    return entry


def list_escalations():
    if not os.path.exists(ESCALATIONS_PATH):
        return []
    with open(ESCALATIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


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
