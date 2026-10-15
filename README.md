# Jarvis — Personal AI Agent (CHAOS Hackathon)

## What it does
Jarvis reads all your Google Calendars, detects conflicts across them,
proposes a new time by email, reads the reply, and either reschedules
the event or escalates with a distinct status. It supports **multi-turn
negotiation** (round 1 → round 2) and a **background watch mode** that
runs propose + check on a schedule.

## Why it is an agent, not a script
- **Background operation:** `watch` mode runs propose + check every N seconds.
- **Handles incomplete information:** ambiguous replies, silence, counter-offers.
- **Recognises failure** with distinct, auditable outcomes:
  `rescheduled`, `declined`, `escalate`, `awaiting_reply`, `counter_proposed`.
- **Idempotent:** never sends duplicate proposals for the same event.
- **Persists state** across runs.
- **Never guesses:** unclear reply → escalate, not invent.

## Architecture
    jarvis/auth.py       OAuth (Calendar + Gmail scopes)
    jarvis/calendar.py   multi-calendar read, conflict detection, event moves
    jarvis/email.py      send proposal, thread-scoped reply read
    jarvis/parse.py      regex reply parser + optional LLM fallback
    jarvis/store.py      pending proposals + escalation log with pruning
    jarvis/retry.py      retry wrapper for transient Google API errors
    jarvis/config.py     runtime config (email, overridable via env / config.json)
    jarvis/agent.py      two-phase CLI pipeline

    webui.py             thin streaming UI  (port 8000)
    webui_form.py        form UI            (port 8001)
    webui_pretty.py      dashboard UI       (port 8002)

## Setup
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Place credentials.json (OAuth desktop client) in the project root.
First run opens a browser for consent and writes token.json.

## CLI
    python reset_calendar.py
    python seed_calendar.py
    python -m jarvis.agent propose
    python -m jarvis.agent check
    python -m jarvis.agent watch --interval 300          # background loop
    python -m jarvis.agent watch --interval 5 --cycles 2 # 2 quick cycles
    python -m jarvis.agent escalations
    python -m jarvis.agent demo --path accept|decline|unclear|no_reply

## Web UIs
    python webui.py         # http://127.0.0.1:8000
    python webui_form.py    # http://127.0.0.1:8001
    python webui_pretty.py  # http://127.0.0.1:8002

## Config
Runtime email is read from (in order):
  1. $env:JARVIS_EMAIL
  2. config.json  ({"my_email": "you@example.com"})
  3. default in jarvis/config.py

## Tests
    python -m unittest discover -s tests -v   # 20 tests

## Known limitations
- Reply parsing is rule-based; LLM fallback is opt-in via OPENAI_API_KEY.
- Negotiation capped at 2 rounds.
- Only Google Calendar + Gmail supported.
- Watch mode runs in the foreground; Ctrl+C to stop.
