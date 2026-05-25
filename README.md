# MoodAnalyser

> Anonymous team wellbeing pulse for remote teams, built on OpenClaw skills.

MoodAnalyser sends fun disguised mood questions to your team via Telegram twice
a week and Woody delivers an aggregated weekly trend report to the manager.
No individual data is ever surfaced — only group trends.

---

## How it works

| When | What happens |
|---|---|
| Tuesday (minute 1 in demo / 10am in production) | Woody sends 5 questions to all team members |
| Thursday (minute 3 in demo / 10am in production) | Woody sends 5 different questions |
| Monday (minute 6 in demo / 9am in production) | Woody sends weekly trend report to manager |

Questions cover 5 dimensions: **mood**, **energy**, **workload**, **connection**, **clarity**.
All responses are anonymised with SHA-256 + private salt before storage.

---

## Requirements

- [OpenClaw](https://openclaw.im) 2026.x+
- Python 3.11+
- A Telegram bot (created via [@BotFather](https://t.me/BotFather))

---

## Setup

### Step 1 — Install OpenClaw

```bash
curl -fsSL https://openclaw.im/install.sh | bash
openclaw onboard --install-daemon
```

### Step 2 — Clone this repo

```bash
git clone https://github.com/yourusername/moodanalyser.git
cd moodanalyser
```

### Step 3 — Install Python dependency

```bash
pip3 install -r requirements.txt --break-system-packages
```

### Step 4 — Create your Telegram bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token BotFather gives you

### Step 5 — Collect team member chat IDs

1. Start `bot.py` (see Step 7)
2. Share your bot username with the team
3. Ask each member to send `/start` to the bot
4. Woody replies with their chat ID — collect all of them

### Step 6 — Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in:
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `MOODANALYSER_MEMBERS` — comma-separated chat IDs from Step 5
- `MANAGER_TELEGRAM_ID` — manager's chat ID
- `MOODANALYSER_SALT` — generate with `openssl rand -hex 32`

### Step 7 — Test it

```bash
# Preview questions without sending anything
python3 skill.py --dry-run

# Send Tuesday batch
python3 skill.py --batch tuesday

# Start the bot listener (in a separate terminal)
python3 bot.py

# Trigger the weekly alert manually
python3 alerts.py
```

### Step 8 — Install into OpenClaw

```bash
openclaw skills install moodanalyser
openclaw skills list
openclaw skills check
```

### Step 9 — Run bot.py as a permanent service

```bash
sudo nano /etc/systemd/system/moodanalyser-bot.service
```

```ini
[Unit]
Description=MoodAnalyser Telegram bot (Woody)
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=PATH_TO_YOUR_WORKING_DIRECTORY
EnvironmentFile=PATH_TO_YOUR_.env_FILE
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable moodanalyser-bot
sudo systemctl start moodanalyser-bot
sudo systemctl status moodanalyser-bot
```

---

## Switching from demo to production schedule

In `.env`, replace the demo schedule lines with production ones:

```bash
SCHEDULE_TUESDAY=0 10 * * 2
SCHEDULE_THURSDAY=0 10 * * 4
SCHEDULE_ALERTS=0 9 * * 1
```

No code changes needed — just update `.env` and restart.

---

## Customising questions

Edit `questions.json` directly. No code changes needed.
Keep 5 questions per batch. Each question needs:
- `id` — unique integer
- `dimension` — one of: mood, energy, workload, connection, clarity
- `text` — the question string
- `options` — exactly 3 options with `label` (string) and `score` (1, 2, or 3)

---

## File structure

| File | Purpose |
|---|---|
| `skill.py` | Pulse sender — Woody sends questions Tue/Thu |
| `bot.py` | Telegram listener — Woody records responses 24/7 |
| `alerts.py` | Weekly report — Woody briefs the manager Monday |
| `db.py` | All SQLite database interactions |
| `utils.py` | Shared helpers (anon ID, week number, etc.) |
| `questions.json` | Question bank — edit freely |
| `SKILL.md` | OpenClaw skill manifest |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

---

## Privacy

- Telegram user IDs are hashed with SHA-256 + private salt before storage
- The salt never leaves your machine
- Managers only see aggregate trends, never individual responses
- All data is stored in a local SQLite database
- Nothing is sent to external servers

---
