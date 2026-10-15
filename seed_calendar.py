from jarvis.auth import get_calendar_service
from datetime import datetime, timedelta, timezone

svc = get_calendar_service()

# Base: tomorrow at 10:00 local time.
# Google needs RFC3339 with timezone offset. We use a fixed +05:30 (IST).
tz = "+05:30"
base = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
def at(h, m):
    t = base.replace(hour=h, minute=m)
    return t.strftime("%Y-%m-%dT%H:%M:%S") + tz

events = [
    {"summary": "Team sync",     "start": at(10, 0), "end": at(11, 0)},
    {"summary": "Design review", "start": at(10, 30), "end": at(11, 30)},  # overlaps Team sync
    {"summary": "Solo focus",    "start": at(15, 0), "end": at(16, 0)},
]

for e in events:
    body = {
        "summary": e["summary"],
        "start": {"dateTime": e["start"], "timeZone": "Asia/Kolkata"},
        "end":   {"dateTime": e["end"],   "timeZone": "Asia/Kolkata"},
    }
    created = svc.events().insert(calendarId="primary", body=body).execute()
    print("created:", created["summary"], "-", created["id"])

# Also create a secondary calendar with one overlapping event on it
cal = svc.calendars().insert(body={"summary": "Rahul Work"}).execute()
cal_id = cal["id"]
print("created calendar:", cal_id)

body = {
    "summary": "Standup",
    "start": {"dateTime": at(10, 15), "timeZone": "Asia/Kolkata"},
    "end":   {"dateTime": at(10, 45), "timeZone": "Asia/Kolkata"},
}
created = svc.events().insert(calendarId=cal_id, body=body).execute()
print("created:", created["summary"], "-", created["id"])
