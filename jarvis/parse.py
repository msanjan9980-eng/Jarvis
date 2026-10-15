"""Parse a reply email body into a structured decision."""
import re
from datetime import datetime, timedelta

YES_PAT = re.compile(r"\b(yes|yep|yeah|sure|ok|okay|accept|confirm(ed)?|works( for me)?|fine|agreed?)\b", re.I)
NO_PAT  = re.compile(r"\b(no|nope|can'?t|cannot|decline|not possible|doesn'?t work|won'?t work|busy)\b", re.I)
TIME_PAT = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm)?\b|\b(\d{1,2})\s*(am|pm)\b", re.I)

QUOTE_CUTS = re.compile(
    r"(^\s*On .+wrote:)|(^\s*From:)|(^\s*-----Original Message-----)|(^\s*_{5,})",
    re.I | re.M,
)


def _strip_quoted(text):
    text = text or ""
    m = QUOTE_CUTS.search(text)
    if m:
        text = text[:m.start()]
    lines = [l for l in text.splitlines() if not l.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _parse_time(text):
    m = TIME_PAT.search(text)
    if not m:
        return None
    if m.group(1) is not None:
        h, mi, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    else:
        h, mi, ampm = int(m.group(4)), 0, (m.group(5) or "").lower()
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def parse_reply(body, reference_date=None):
    clean = _strip_quoted(body)
    hm = _parse_time(clean)
    yes = bool(YES_PAT.search(clean))
    no = bool(NO_PAT.search(clean))

    if yes and not no:
        return {"decision": "accept", "new_start": None, "raw": clean}
    if no:
        return {"decision": "decline", "raw": clean}
    if hm:
        ref = reference_date or datetime.now()
        start = ref.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        if start < ref:
            start += timedelta(days=1)
        return {"decision": "propose_time", "new_start": start, "raw": clean}
    return {"decision": "unclear", "raw": clean}


MY_ADDRESS = "msanjan9980@gmail.com"


def decide_from_replies(replies, reference_date=None):
    """Read the latest reply. Assumes the caller has already scoped to a single thread
    and excluded the original proposal message."""
    if not replies:
        return {"decision": "no_reply"}
    latest = replies[-1]
    result = parse_reply(latest["body"], reference_date=reference_date)
    result["from"] = latest.get("from")
    result["subject"] = latest.get("subject")
    return result
