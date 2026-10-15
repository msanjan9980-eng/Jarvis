from jarvis.auth import get_calendar_service

svc = get_calendar_service()
names = {"Team sync", "Design review", "Solo focus"}
now = "2026-01-01T00:00:00Z"

events = svc.events().list(calendarId="primary", timeMin=now, singleEvents=True).execute().get("items", [])
for e in events:
    if e.get("summary") in names:
        svc.events().delete(calendarId="primary", eventId=e["id"]).execute()
        print("deleted:", e.get("summary"))

# Delete the Rahul Work calendar too
cals = svc.calendarList().list().execute().get("items", [])
for c in cals:
    if c.get("summary") == "Rahul Work":
        svc.calendars().delete(calendarId=c["id"]).execute()
        print("deleted calendar: Rahul Work")


# Clear stored state so we start from a clean slate
import os
base = os.path.dirname(os.path.abspath(__file__))
for fname in ("pending.json", "escalations.json"):
    p = os.path.join(base, "jarvis", fname)
    if os.path.exists(p):
        os.remove(p)
        print(f"cleared: jarvis/{fname}")
