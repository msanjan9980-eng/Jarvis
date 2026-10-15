# Jarvis — Personal AI Agent (CHAOS Hackathon)

## What it does
Jarvis reads all of your Google Calendars, detects conflicts across them,
proposes a new time by email, reads the reply, and either reschedules the
event or escalates with a distinct status. It supports **multi-turn
negotiation**: if you counter with a different time, Jarvis sends a
follow-up proposal and waits for the second reply.

## Why it is an agent, not a script
- Handles incomplete information (ambiguous replies, silence, counter-offers).
- **Recognises failure** with distinct, auditable outcomes:
  `rescheduled`, `declined`, `escalate` (unclear reply), `awaiting_reply`
  (no response), `counter_proposed` (round 1 → round 2).
- Shows a step-by-step reasoning trace at every stage.
- Persists state (`pending.json`, `escalations.json`) so it survives across runs.
- Never guesses: if the reply is unclear, it escalates rather than inventing a decision.

## Architecture
    jarvis/auth.py       OAuth (Calendar + Gmail scopes)
    jarvis/calendar.py   multi-calendar read, conflict detection, event moves
    jarvis/email.py      send proposal, thread-scoped reply read
    jarvis/parse.py      regex reply parser + optional LLM fallback
    jarvis/store.py      pending proposals + escalation log with pruning
    jarvis/retry.py      retry wrapper for transient Google API errors
    jarvis/agent.py      two-phase CLI pipeline

    webui.py             thin streaming UI (2 buttons, live SSE trace)
    webui_form.py        form UI (pick conflict, pick time, simulate reply)

## Run

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Place `credentials.json` (Google OAuth desktop client) in the project root.
First run opens a browser for consent and writes `token.json`.

## CLI

    python reset_calendar.py            # clear demo state
    python seed_calendar.py             # create 3 overlapping test events + 1 cross-calendar
    python -m jarvis.agent propose      # phase 1: send proposals
    python -m jarvis.agent check        # phase 2: read replies and act
    python -m jarvis.agent escalations  # list logged escalations
    python -m jarvis.agent demo --path accept|decline|unclear|no_reply
                                        # offline demo of each failure path

## Web UIs

    python webui.py        # http://127.0.0.1:8000 — two buttons, live streaming log
    python webui_form.py   # http://127.0.0.1:8001 — pick conflict/time, simulate reply

## Tests

    python -m unittest discover -s tests -v   # 20 tests

## Known limitations
- Reply parsing is rule-based (regex); the LLM fallback is opt-in via
  `OPENAI_API_KEY` and never runs on the deterministic path.
- Negotiation is capped at 2 rounds; a round-2 counter escalates.
- Only Google Calendar + Gmail are supported.
- Does not treat all-day events as conflicts (by design).
