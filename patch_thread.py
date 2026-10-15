"""Scope replies to their own proposal thread."""
path = r"C:\JARVIS 2.0\jarvis\email.py"
src = open(path, encoding="utf-8").read()

if "def list_replies_for_thread" not in src:
    add = '''

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
'''
    src = src + add
    open(path, "w", encoding="utf-8").write(src)
    print("patched jarvis/email.py")

# Now patch agent.check_only to use per-thread replies
apath = r"C:\JARVIS 2.0\jarvis\agent.py"
asrc = open(apath, encoding="utf-8").read()

if "list_replies_for_thread" not in asrc:
    asrc = asrc.replace(
        "from jarvis.email import send_proposal, list_replies",
        "from jarvis.email import send_proposal, list_replies, list_replies_for_thread"
    )
    asrc = asrc.replace(
        "    replies = list_replies()\n    _log(f\"  {len(replies)} marker message(s)\")\n    results = []\n    for p in pending:\n        new_start = datetime.fromisoformat(p[\"new_start_iso\"])\n        decision = decide_from_replies(replies, reference_date=new_start)",
        "    results = []\n    for p in pending:\n        replies = list_replies_for_thread(p[\"proposal_msg_id\"])\n        _log(f\"  '{p['summary']}' -> {len(replies)} reply(ies) in thread\")\n        new_start = datetime.fromisoformat(p[\"new_start_iso\"])\n        decision = decide_from_replies(replies, reference_date=new_start)"
    )
    open(apath, "w", encoding="utf-8").write(asrc)
    print("patched jarvis/agent.py")
else:
    print("agent already patched")
