---
name: MoodAnalyser
description: Anonymous team wellbeing pulse for remote teams built on OpenClaw.
Sends fun disguised mood questions via Telegram twice a week and delivers
an aggregated weekly trend report to the team manager.
---

# MoodAnalyser

Anonymous team wellbeing pulse for remote teams built on OpenClaw.
Sends fun disguised mood questions via Telegram twice a week and delivers
an aggregated weekly trend report to the team manager.
No individual data is ever surfaced.

## Skills

### moodanalyser
Sends 5 questions to all team members every Tuesday and Thursday.
Covers 5 dimensions: mood, energy, workload, connection, clarity.

**Trigger:** Cron — configured via SCHEDULE_TUESDAY and SCHEDULE_THURSDAY in .env
**Entry:** skill.py
**Runtime:** python

### moodanalyser-bot
Persistent Telegram long-poll listener. Receives button taps,
records anonymised responses to SQLite, removes buttons after tap.

**Trigger:** Always-on daemon
**Entry:** bot.py
**Runtime:** python

### moodanalyser-alerts
Weekly report for the manager: overall score, dimension breakdown,
participation rate, streak detection, and intervention advice.

**Trigger:** Cron — configured via SCHEDULE_ALERTS in .env
**Entry:** alerts.py
**Runtime:** python

## Environment variables

| Variable              | Description                                              |
|-----------------------|----------------------------------------------------------|
| TELEGRAM_BOT_TOKEN    | Bot token from @BotFather                                |
| MOODANALYSER_SALT       | Random secret for hashing user IDs — never change        |
| MOODANALYSER_MEMBERS    | Comma-separated Telegram chat IDs of team members        |
| MANAGER_TELEGRAM_ID   | Manager's Telegram chat ID                               |
| SCHEDULE_TUESDAY      | Cron for Tuesday pulse  (demo: "1 * * * *")              |
| SCHEDULE_THURSDAY     | Cron for Thursday pulse (demo: "2 * * * *")              |
| SCHEDULE_ALERTS       | Cron for weekly report  (demo: "5 * * * *")              |
| MOODANALYSER_DB         | Optional: custom SQLite path                             |

## Requirements

- OpenClaw 2026.x+
- Python 3.11+
- pip: requests

## Files

| File           | Purpose                                   |
|----------------|-------------------------------------------|
| skill.py       | Pulse sender                              |
| bot.py         | Telegram response listener                |
| alerts.py      | Weekly manager report                     |
| db.py          | All database interactions                 |
| utils.py       | Shared helpers                            |
| questions.json | Question bank — edit freely               |
| requirements.txt | Python dependencies                     |
| .env.example   | Environment variable template             |