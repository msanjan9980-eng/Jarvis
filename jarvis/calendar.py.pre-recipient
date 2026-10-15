"""Calendar read + conflict detection + event update."""
from datetime import datetime, timedelta
from jarvis.auth import get_calendar_service

# How far ahead to look for conflicts (days)
LOOKAHEAD_DAYS = 7


def _parse(dt_str):
    """Parse RFC3339 datetime from Google. Returns aware datetime or None."""
    if not dt_str:
        return None
    # Google returns e.g. 2026-10-16T10:00:00+05:30 or ...Z
    s = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def list_calendars():
    svc = get_calendar_service()
    return svc.calendarList().list().execute().get("items", [])


def list_events(days=LOOKAHEAD_DAYS):
    """Return all timed events across all calendars in the next N days."""
    svc = get_calendar_service()
    now = datetime.now().astimezone()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    out = []
    for cal in list_calendars():
        cal_id = cal["id"]
        cal_name = cal.get("summary", cal_id)
        items = svc.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])
        for e in items:
            start = _parse(e.get("start", {}).get("dateTime"))
            end = _parse(e.get("end", {}).get("dateTime"))
            if not start or not end:
                continue  # skip all-day events; they are not "conflicts"
            out.append({
                "id": e["id"],
                "calendar_id": cal_id,
                "calendar": cal_name,
                "summary": e.get("summary", "(no title)"),
                "start": start,
                "end": end,
                "attendees": [a.get("email") for a in e.get("attendees", []) if a.get("email")],
            })
    out.sort(key=lambda x: x["start"])
    return out


def find_conflicts(events):
    """Return list of (event_a, event_b) pairs that overlap in time."""
    conflicts = []
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            a, b = events[i], events[j]
            # Overlap if a.start < b.end AND b.start < a.end
            if a["start"] < b["end"] and b["start"] < a["end"]:
                conflicts.append((a, b))
    return conflicts


def print_conflicts(conflicts):
    if not conflicts:
        print("No conflicts found.")
        return
    print(f"Found {len(conflicts)} conflict(s):")
    for a, b in conflicts:
        print(f"  [{a['summary']}] {a['start']:%Y-%m-%d %H:%M} - {a['end']:%H:%M}  ({a['calendar']})")
        print(f"  [{b['summary']}] {b['start']:%Y-%m-%d %H:%M} - {b['end']:%H:%M}  ({b['calendar']})")
        print()
