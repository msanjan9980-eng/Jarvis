"""Send an acknowledgment when the recipient declines."""

# --------------------------------------------------------------------------
# 1) jarvis/email.py — add send_decline_acknowledgment
# --------------------------------------------------------------------------
epath = r"C:\JARVIS 2.0\jarvis\email.py"
esrc = open(epath, encoding="utf-8").read()

if "def send_decline_acknowledgment(" not in esrc:
    esrc += '''

def send_decline_acknowledgment(to_email, summary, in_reply_to_msg_id=None):
    """Reply when the recipient declined. Keeps the thread open and asks
    for an alternative time so the negotiation can continue."""
    svc = get_gmail_service()
    subject = f"{SUBJECT_MARKER} Re: {summary} — noted, will follow up"
    body = f"""Hi,

Thanks for letting me know. Sorry the proposed time didn't work for "{summary}".

I'll look into other options and get back to you shortly.

In the meantime — are there any times that would work better for you?
Just reply with a suggested slot and I'll re-propose it.

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
    print("email.py: added send_decline_acknowledgment")
else:
    print("email.py: already has send_decline_acknowledgment")


# --------------------------------------------------------------------------
# 2) jarvis/agent.py — call it on the decline branch
# --------------------------------------------------------------------------
apath = r"C:\JARVIS 2.0\jarvis\agent.py"
asrc = open(apath, encoding="utf-8").read()

if "send_decline_acknowledgment" not in asrc:
    asrc = asrc.replace(
        "from jarvis.email import send_proposal, list_replies, list_replies_for_thread, send_confirmation",
        "from jarvis.email import send_proposal, list_replies, list_replies_for_thread, send_confirmation, send_decline_acknowledgment"
    )
    old_decline = '''        if d == "decline":
            store.mark_resolved(p["proposal_msg_id"], "declined")
            store.log_escalation({"event": p["summary"], "reason": "declined",
                                  "proposal_msg_id": p["proposal_msg_id"]})'''
    new_decline = '''        if d == "decline":
            try:
                recipient = p.get("recipient") or MY_EMAIL
                send_decline_acknowledgment(recipient, p["summary"],
                                            in_reply_to_msg_id=p.get("proposal_msg_id"))
                _log(f"    sent decline acknowledgment to {recipient}")
            except Exception as e:
                _log(f"    decline acknowledgment failed: {e!r}")
            store.mark_resolved(p["proposal_msg_id"], "declined")
            store.log_escalation({"event": p["summary"], "reason": "declined",
                                  "proposal_msg_id": p["proposal_msg_id"]})'''
    if old_decline in asrc:
        asrc = asrc.replace(old_decline, new_decline)
        open(apath, "w", encoding="utf-8").write(asrc)
        print("agent.py: decline branch sends acknowledgment")
    else:
        print("agent.py: decline pattern not found — check file")
else:
    print("agent.py: already has send_decline_acknowledgment")


# --------------------------------------------------------------------------
# 3) site.py — simulated decline path
# --------------------------------------------------------------------------
spath = r"C:\JARVIS 2.0\site.py"
ssrc = open(spath, encoding="utf-8").read()

if "send_decline_acknowledgment" not in ssrc:
    ssrc = ssrc.replace(
        "from jarvis.email import send_proposal, send_confirmation",
        "from jarvis.email import send_proposal, send_confirmation, send_decline_acknowledgment"
    )
    old_site = '''            elif d["decision"] == "decline":
                store.mark_resolved(p["proposal_msg_id"], "declined")
                store.log_escalation({"event": p["summary"], "reason": "declined", "proposal_msg_id": p["proposal_msg_id"]})'''
    new_site = '''            elif d["decision"] == "decline":
                try:
                    recipient = p.get("recipient") or config.my_email()
                    send_decline_acknowledgment(recipient, p["summary"],
                                                in_reply_to_msg_id=p.get("proposal_msg_id"))
                    print(f"[ui] sent decline acknowledgment to {recipient}")
                except Exception as e:
                    print(f"[ui] decline acknowledgment failed: {e!r}")
                store.mark_resolved(p["proposal_msg_id"], "declined")
                store.log_escalation({"event": p["summary"], "reason": "declined", "proposal_msg_id": p["proposal_msg_id"]})'''
    if old_site in ssrc:
        ssrc = ssrc.replace(old_site, new_site)
        open(spath, "w", encoding="utf-8").write(ssrc)
        print("site.py: decline branch sends acknowledgment")
    else:
        print("site.py: decline pattern not found — check file")
else:
    print("site.py: already has send_decline_acknowledgment")
