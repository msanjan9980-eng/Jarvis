from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

SCOPES = ["https://www.googleapis.com/auth/calendar"]

creds = None
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
    with open("token.json", "w") as f:
        f.write(creds.to_json())

service = build("calendar", "v3", credentials=creds)
events = service.events().list(
    calendarId="primary", maxResults=5, singleEvents=True, orderBy="startTime"
).execute()
items = events.get("items", [])
if not items:
    print("No events found. Add one to your calendar for the demo.")
for e in items:
    print(e.get("summary"), "-", e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"))
