"""Two fixes: (a) decide_from_replies should not filter replies in an already-scoped thread.
(b) agent.check_only should trust decide_from_replies fully."""
path = r"C:\JARVIS 2.0\jarvis\parse.py"
src = open(path, encoding="utf-8").read()

# Replace decide_from_replies with a simpler version that trusts the caller.
old_fn_marker = "def decide_from_replies(replies, reference_date=None):"
if old_fn_marker in src:
    idx = src.index(old_fn_marker)
    # cut everything from decide_from_replies to end of file
    src = src[:idx] + '''def decide_from_replies(replies, reference_date=None):
    """Read the latest reply. Assumes the caller has already scoped to a single thread
    and excluded the original proposal message."""
    if not replies:
        return {"decision": "no_reply"}
    latest = replies[-1]
    result = parse_reply(latest["body"], reference_date=reference_date)
    result["from"] = latest.get("from")
    result["subject"] = latest.get("subject")
    return result
'''
    open(path, "w", encoding="utf-8").write(src)
    print("patched jarvis/parse.py")
else:
    print("parse.py already patched")
