"""Wire execute_with_retry into the Gmail send call."""
path = r"C:\JARVIS 2.0\jarvis\email.py"
src = open(path, encoding="utf-8").read()

if "execute_with_retry" not in src:
    src = src.replace(
        "from jarvis.auth import get_gmail_service",
        "from jarvis.auth import get_gmail_service\nfrom jarvis.retry import execute_with_retry"
    )
    src = src.replace(
        'sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()',
        'sent = execute_with_retry(svc.users().messages().send(userId="me", body={"raw": raw}))'
    )
    open(path, "w", encoding="utf-8").write(src)
    print("patched jarvis/email.py")
else:
    print("email.py already patched")
