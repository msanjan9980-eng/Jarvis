"""Tier 1 patches for jarvis/agent.py: config, dedup, watch mode."""
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()
changes = []

# --- 1) import config ---
if "from jarvis import config" not in src:
    src = src.replace(
        "from jarvis import store",
        "from jarvis import store\nfrom jarvis import config"
    )
    changes.append("import config")

# --- 2) MY_EMAIL from config ---
if 'MY_EMAIL = "msanjan9980@gmail.com"' in src:
    src = src.replace(
        'MY_EMAIL = "msanjan9980@gmail.com"',
        "MY_EMAIL = config.my_email()"
    )
    changes.append("MY_EMAIL from config")

# --- 3) dedup helper + usage ---
if "def _has_pending_proposal(" not in src:
    helper = '''

def _has_pending_proposal(event_id):
    """True if a proposal for this event is still awaiting a reply."""
    for p in store.pending_only():
        if p.get("event_id") == event_id:
            return True
    return False


'''
    # insert helper right before "def propose_only("
    src = src.replace("def propose_only(", helper + "def propose_only(", 1)
    changes.append("dedup helper")

    # use it inside propose_only loop
    old = '''    for a, b in conflicts:
        _log(f"  conflict: '{a['summary']}' vs '{b['summary']}'")
        new_start, new_end = propose_new_time(a, b)'''
    new = '''    for a, b in conflicts:
        _log(f"  conflict: '{a['summary']}' vs '{b['summary']}'")
        if _has_pending_proposal(a["id"]):
            _log(f"  skip: a proposal for '{a['summary']}' is already pending")
            continue
        new_start, new_end = propose_new_time(a, b)'''
    if old in src:
        src = src.replace(old, new)
        changes.append("dedup in propose_only")
    else:
        changes.append("!!! dedup loop not found — skipped")

# --- 4) watch mode function ---
if "def watch(" not in src:
    watch_fn = '''

def watch(interval=60, cycles=None):
    """Run propose + check in a loop. Ctrl+C to stop."""
    import time
    n = 0
    try:
        while cycles is None or n < cycles:
            n += 1
            _log(f"=== WATCH CYCLE {n} ===")
            try:
                propose_only()
            except Exception as e:
                _log(f"  propose failed: {e!r}")
            try:
                check_only()
            except Exception as e:
                _log(f"  check failed: {e!r}")
            if cycles is not None and n >= cycles:
                break
            _log(f"  sleeping {interval}s (Ctrl+C to stop)...")
            time.sleep(interval)
    except KeyboardInterrupt:
        _log("watch stopped by user")


'''
    src = src.replace("def main(", watch_fn + "def main(", 1)
    changes.append("watch function")

# --- 5) subparser + handler ---
if 'add_parser("watch"' not in src:
    src = src.replace(
        '    p_demo = sub.add_parser("demo", help="force a failure path")',
        '    p_watch = sub.add_parser("watch", help="run propose+check on a loop")\n'
        '    p_watch.add_argument("--interval", type=int, default=60, help="seconds between cycles")\n'
        '    p_watch.add_argument("--cycles", type=int, default=None, help="stop after N cycles")\n\n'
        '    p_demo = sub.add_parser("demo", help="force a failure path")'
    )
    src = src.replace(
        '    elif args.cmd == "demo":\n        demo(args.path)',
        '    elif args.cmd == "watch":\n        watch(interval=args.interval, cycles=args.cycles)\n'
        '    elif args.cmd == "demo":\n        demo(args.path)'
    )
    changes.append("watch subcommand")

open(path, "w", encoding="utf-8").write(src)
print("agent.py changes:", ", ".join(changes))
