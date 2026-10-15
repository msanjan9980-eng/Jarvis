# Jarvis — Personal AI Agent (CHAOS Hackathon)

## What it does
Jarvis detects conflicts across all your Google Calendars, proposes a new time by email,
reads the reply, and either reschedules the event or escalates to you.

## Why it's an agent, not a script
- Handles incomplete info (ambiguous replies).
- Recognises failure: declined / unclear / no_reply / counter_proposed are distinct
  outcomes, each handled differently. It does not guess.
- Shows its reasoning at every step.

## Run
    python seed_calendar.py
    python -m jarvis.agent run
    python -m jarvis.agent run --all
    python -m jarvis.agent run --dry
    python -m jarvis.agent demo --path accept|decline|unclear|no_reply|counter
    python reset_calendar.py

## Tests
    python -m unittest tests.test_parse -v

## Setup
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Place credentials.json (Google OAuth desktop client) in project root.
First run opens browser for consent and writes token.json.
