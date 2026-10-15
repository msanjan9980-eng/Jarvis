"""Runtime configuration for Jarvis.

Priority (highest wins):
  1. JARVIS_EMAIL environment variable
  2. config.json in project root
  3. hardcoded default below

Edit the default, or drop a config.json with {"my_email": "you@example.com"}
in the project root, or set $env:JARVIS_EMAIL before running the agent.
"""
import json
import os

_DEFAULTS = {
    "my_email": "msanjan9980@gmail.com",
}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_ROOT, "config.json")


def _load():
    cfg = dict(_DEFAULTS)
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[config] could not read config.json: {e}")
    env = os.environ.get("JARVIS_EMAIL")
    if env:
        cfg["my_email"] = env
    return cfg


_cfg = _load()


def my_email():
    return _cfg["my_email"]
