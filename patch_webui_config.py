"""Route both web UIs through config.my_email()."""
for path, old_call, new_call in [
    (r"C:\JARVIS 2.0\webui_form.py",
     'send_proposal("msanjan9980@gmail.com"',
     'send_proposal(config.my_email()'),
    (r"C:\JARVIS 2.0\webui_pretty.py",
     'MY_EMAIL = "msanjan9980@gmail.com"',
     'MY_EMAIL = config.my_email()'),
]:
    src = open(path, encoding="utf-8").read()
    changed = False
    if "from jarvis import config" not in src:
        src = src.replace("from jarvis import store", "from jarvis import store\nfrom jarvis import config")
        changed = True
    if old_call in src:
        src = src.replace(old_call, new_call)
        changed = True
    open(path, "w", encoding="utf-8").write(src)
    print(path, "->", "patched" if changed else "already clean")
