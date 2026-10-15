"""Gmail send + read for the reschedule proposal flow."""
import base64
from email.mime.text import MIMEText
from jarvis.auth import get_gmail_service

SUBJECT_MARKER = "[JARVIS-RESCHEDULE]"


def send_proposal(to_email, conflict, proposed_start, proposed_end):
    """Send a proposal email. Returns the Gmail message id."""
    svc = get_gmail_service()

    subject = f"{SUBJECT_MARKER} Reschedule {conflict['summary']}?"
    body = f"""Hi,

Your event "{conflict['summary']}" is currently scheduled at
    {conflict['start']:%A %d %b, %H:%M} - {conflict['end']:%H:%M}

This overlaps with another event on your calendar. Can we move it to:
    {proposed_start:%A %d %b, %H:%M} - {proposed_end:%H:%M}?

Please reply with one of:
  - YES to accept the new time
  - NO to decline
  - or a specific new time (e.g. "How about 14:00?")

— Jarvis
"""
    msg = MIMEText(body)
    msg["to"] = to_email
    msg["subject"] = subject
    msg["from"] = "me"

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]


def list_replies():
    """Return list of dicts: {id, subject, body, from} for messages matching the marker."""
    svc = get_gmail_service()
    query = f'subject:"{SUBJECT_MARKER}"'
    resp = svc.users().messages().list(userId="me", q=query, maxResults=20).execute()
    out = []
    for m in resp.get("messages", []):
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        body = _extract_body(full["payload"])
        out.append({
            "id": m["id"],
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "snippet": full.get("snippet", ""),
            "body": body,
            "internal_date": int(full.get("internalDate", "0")),
        })
    out.sort(key=lambda x: x["internal_date"])
    return out


def _extract_body(payload):
    """Walk MIME parts and return the text/plain body."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        body = _extract_body(part)
        if body:
            return body
    return ""


def list_replies_for_thread(proposal_msg_id):
    """Return replies whose Gmail threadId matches the original proposal's thread."""
    svc = get_gmail_service()
    orig = svc.users().messages().get(userId="me", id=proposal_msg_id, format="metadata").execute()
    tid = orig.get("threadId")
    if not tid:
        return []
    thread = svc.users().threads().get(userId="me", id=tid, format="full").execute()
    out = []
    for m in thread.get("messages", []):
        if m["id"] == proposal_msg_id:
            continue  # skip the original send
        headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
        body = _extract_body(m["payload"])
        out.append({
            "id": m["id"],
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "snippet": m.get("snippet", ""),
            "body": body,
            "internal_date": int(m.get("internalDate", "0")),
        })
    out.sort(key=lambda x: x["internal_date"])
    return out
