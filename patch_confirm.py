"""Add confirmation email sent after a successful reschedule."""

# --------------------------------------------------------------------------
# 1) jarvis/email.py — add send_confirmation
# --------------------------------------------------------------------------
epath = r"C:\JARVIS 2.0\jarvis\email.py"
esrc = open(epath, encoding="utf-8").read()

if "def send_confirmation(" not in esrc:
    esrc += '''

def send_confirmation(to_email, summary, new_start, new_end, in_reply_to_msg_id=None):
    """Send a confirmation reply after the event has been moved.

    Places the confirmation in the same Gmail thread as the original proposal
    so the conversation stays coherent.
    """
    svc = get_gmail_service()
    subject = f"{SUBJECT_MARKER} Confirmed: {summary}"
    body = f"""Hi,

Confirmed. The event "{summary}" has been moved to:

    {new_start:%A %d %b, %H:%M} - {new_end:%H:%M}

No further action needed.

— Jarvis
"""
    msg = MIMEText(body)
    msg["to"] = to_email
    msg["subject"] = subject
    msg["from"] = "me"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    send_body = {"raw": raw}
    if in_reply_to_msg_id:
        try:
            orig = svc.users().messages().get(userId="me", id=in_reply_to_msg_id, format="metadata").execute()
            tid = orig.get("threadId")
            if tid:
                send_body["threadId"] = tid
        except Exception:
            pass

    sent = execute_with_retry(svc.users().messages().send(userId="me", body=send_body))
    return sent["id"]
'''
    open(epath, "w", encoding="utf-8").write(esrc)
    print("email.py: added send_confirmation")
else:
    print("email.py: already has send_confirmation")


# --------------------------------------------------------------------------
# 2) jarvis/agent.py — call it inside _do_move
# --------------------------------------------------------------------------
apath = r"C:\JARVIS 2.0\jarvis\agent.py"
asrc = open(apath, encoding="utf-8").read()

if "send_confirmation" not in asrc:
    # add to imports
    asrc = asrc.replace(
        "from jarvis.email import send_proposal, list_replies, list_replies_for_thread",
        "from jarvis.email import send_proposal, list_replies, list_replies_for_thread, send_confirmation"
    )
    # patch _do_move: add confirmation send after successful patch
    old_move = '''    svc.events().patch(
        calendarId=p["calendar_id"], eventId=p["event_id"],
        body={"start": {"dateTime": new_start.isoformat(), "timeZone": "Asia/Kolkata"},
              "end": {"dateTime": (new_start + dur).isoformat(), "timeZone": "Asia/Kolkata"}},
    ).execute()
    _log(f"    moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")'''
    new_move = '''    svc.events().patch(
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
        _log(f"    confirmation send failed: {e!r}")'''
    if old_move in asrc:
        asrc = asrc.replace(old_move, new_move)
        open(apath, "w", encoding="utf-8").write(asrc)
        print("agent.py: _do_move sends confirmation")
    else:
        print("agent.py: _do_move pattern not found — check file")
else:
    print("agent.py: already has send_confirmation")


# --------------------------------------------------------------------------
# 3) site.py — call it in the simulated move path
# --------------------------------------------------------------------------
spath = r"C:\JARVIS 2.0\site.py"
ssrc = open(spath, encoding="utf-8").read()

if "send_confirmation" not in ssrc:
    ssrc = ssrc.replace(
        "from jarvis.email import send_proposal",
        "from jarvis.email import send_proposal, send_confirmation"
    )
    old_site_move = '''                store.mark_resolved(p["proposal_msg_id"], "rescheduled")
                print(f"[ui] moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")'''
    new_site_move = '''                store.mark_resolved(p["proposal_msg_id"], "rescheduled")
                print(f"[ui] moved '{p['summary']}' to {new_start:%a %d %b %H:%M}")
                try:
                    recipient = p.get("recipient") or config.my_email()
                    send_confirmation(recipient, p["summary"], new_start, new_start + dur,
                                      in_reply_to_msg_id=p.get("proposal_msg_id"))
                    print(f"[ui] sent confirmation to {recipient}")
                except Exception as e:
                    print(f"[ui] confirmation send failed: {e!r}")'''
    if old_site_move in ssrc:
        ssrc = ssrc.replace(old_site_move, new_site_move)
        open(spath, "w", encoding="utf-8").write(ssrc)
        print("site.py: simulated move sends confirmation")
    else:
        print("site.py: simulated-move pattern not found — check file")
else:
    print("site.py: already has send_confirmation")
