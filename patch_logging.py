"""Patch jarvis/agent.py to add file logging."""
import re
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()

if "import logging" in src:
    print("already patched")
else:
    # Add imports after the existing "import argparse"
    src = src.replace(
        "import argparse\nimport sys",
        "import argparse\nimport logging\nimport os\nimport sys"
    )
    # Replace _log with a version that also logs to file
    old = 'def _log(msg):\n    print(f"[jarvis] {msg}", flush=True)'
    new = (
        'LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")\n'
        'os.makedirs(LOG_DIR, exist_ok=True)\n'
        'logging.basicConfig(\n'
        '    filename=os.path.join(LOG_DIR, "jarvis.log"),\n'
        '    level=logging.INFO,\n'
        '    format="%(asctime)s %(message)s",\n'
        ')\n\n\n'
        'def _log(msg):\n'
        '    print(f"[jarvis] {msg}", flush=True)\n'
        '    logging.info(msg)'
    )
    if old not in src:
        print("ERROR: could not find _log to replace")
    else:
        src = src.replace(old, new)
        open(path, "w", encoding="utf-8").write(src)
        print("patched jarvis/agent.py")
