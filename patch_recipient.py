"""Add attendee-aware recipient selection.

Reads the 'attendees' field from the conflict event. Emails the first
attendee who isn't you. Falls back to you (self-loop) if no other
attendees exist, so the existing demo still works.
"""
import os

def patch_calendar():
    path = r"C:\JARVIS 2.0\jarvis\calendar.py"
    src = open(path, encoding="utf-8").read()
    if "def pick_recipient(" in src:
        print("calendar.py: already has pick_recipient")
        return True
    addition = '''

def pick_recipient(event, me):
    """Choose who to email about this event.

    Returns the first attendee that isn't 'me' (case-insensitive).
    Falls back to 'me' if the event has no other attendees, which keeps
    the self-loop demo working when you have no guests on the event.
    """
    me_l = (me or "").lower()
    others = [a for a in event.get("attendees", [])
              if a and a.lower() != me_l]
    return others[0] if others else me
'''
    src = src + addition
    open(path, "w", encoding="utf-8").write(src)
    print("calendar.py: added pick_recipient")
    return True


def patch_agent():
    path = r"C:\JARVIS 2.0\jarvis\agent.py"
    src = open(path, encoding="utf-8").read()

    # 1) import pick_recipient
    if "pick_recipient" not in src:
        old = "from jarvis.calendar import list_events, find_conflicts"
        new = "from jarvis.calendar import list_events, find_conflicts, pick_recipient"
        if old not in src:
            print("agent.py: import line not found — ABORT")
            return False
        src = src.replace(old, new)
        print("agent.py: import updated")

    # 2) replace the send line inside propose_only
    old_send = '''        new_start, new_end = propose_new_time(a, b)
        msg_id = send_proposal(MY_EMAIL, a, new_start, new_end)
        _log(f"  sent proposal id={msg_id} proposing {new_start:%a %d %b %H:%M}")
        store.add_pending({
            "event_id": a["id"],
            "calendar_id": a["calendar_id"],
            "summary": a["summary"],
            "new_start_iso": new_start.isoformat(),
            "proposal_msg_id": msg_id,
        })'''

    new_send = '''        new_start, new_end = propose_new_time(a, b)
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
        })'''

    if old_send in src:
        src = src.replace(old_send, new_send)
        print("agent.py: send line updated")
    else:
        print("agent.py: send block not found — ABORT")
        return False

    open(path, "w", encoding="utf-8").write(src)
    return True


def patch_webui_form():
    path = r"C:\JARVIS 2.0\webui_form.py"
    src = open(path, encoding="utf-8").read()

    if "pick_recipient" in src:
        print("webui_form.py: already patched")
        return True

    # import
    old_imp = "from jarvis.calendar import list_events, find_conflicts"
    new_imp = "from jarvis.calendar import list_events, find_conflicts, pick_recipient"
    if old_imp not in src:
        print("webui_form.py: import line not found — ABORT")
        return False
    src = src.replace(old_imp, new_imp)

    # send call
    old_call = '''        msg_id = send_proposal(config.my_email(), a, new_start, new_end)'''
    new_call = '''        recipient = pick_recipient(a, config.my_email())
        print(f"[webui] recipient: {recipient}")
        msg_id = send_proposal(recipient, a, new_start, new_end)'''
    if old_call not in src:
        print("webui_form.py: send call not found — ABORT")
        return False
    src = src.replace(old_call, new_call)

    open(path, "w", encoding="utf-8").write(src)
    print("webui_form.py: patched")
    return True


ok_c = patch_calendar()
ok_a = patch_agent()
ok_w = patch_webui_form()
print()
print("RESULT:", "ALL OK" if (ok_c and ok_a and ok_w) else "SOME FILES SKIPPED — read above")
