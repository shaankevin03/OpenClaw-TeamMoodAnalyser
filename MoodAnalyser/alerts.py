"""
alerts.py — MoodAnalyser weekly alert generator

Computes weekly trends and sends a structured report to the manager.
Covers: overall score, dimension breakdown, participation rate, streak detection.
Woody delivers all reports. Individual data is never surfaced.

Schedule is configurable via environment variable (set in .env):
  SCHEDULE_ALERTS  cron for the report  (default: "5 * * * *" — minute 5 of every hour)

Production value:
  SCHEDULE_ALERTS=0 9 * * 1   (Monday 9am)
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import logging
import os

import requests

import db
import utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("moodanalyser.alerts")

# ── Config ─────────────────────────────────────────────────────────────────

BOT_TOKEN       = os.environ["TELEGRAM_BOT_TOKEN"]
MANAGER_CHAT_ID = os.environ["MANAGER_TELEGRAM_ID"]
TG_API          = f"https://api.telegram.org/bot{BOT_TOKEN}"

SCHEDULE_ALERTS = os.environ.get("SCHEDULE_ALERTS", "5 * * * *")

ALERT_DELTA        = -0.4
ALERT_LOW          = 1.8
PARTICIPATION_WARN = 0.5
STREAK_WEEKS       = 3
MIN_RESPONSES      = 3


# ── Telegram helper ────────────────────────────────────────────────────────

def send_to_manager(text: str):
    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id":    MANAGER_CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )


# ── Formatting helpers ─────────────────────────────────────────────────────

def score_bar(score: float | None) -> str:
    if score is None:
        return "\u2014 no data"
    bars = ["", "\u2590\u258f\u258f", "\u2590\u2590\u258f", "\u2590\u2590\u2590"]
    return f"{bars[round(score)]} {score:.1f}/3"


def rate_bar(rate: float) -> str:
    filled = round(rate * 10)
    return "\u2588" * filled + "\u2591" * (10 - filled) + f"  {rate * 100:.0f}%"


def avg(values: list) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


# ── Stats ──────────────────────────────────────────────────────────────────

def get_stats(week_num: int) -> dict | None:
    rows           = db.get_week_responses(week_num)
    sent_count     = db.get_sent_count(week_num)
    responses      = list(rows)
    response_count = len(responses)

    if response_count < MIN_RESPONSES:
        return None

    participation = response_count / sent_count if sent_count > 0 else 0.0

    by_dim = {}
    for dim in ["mood", "energy", "workload", "connection", "clarity"]:
        scores      = [r["score"] for r in responses if r["dimension"] == dim]
        by_dim[dim] = avg(scores)

    return {
        "week_num":       week_num,
        "avg_score":      avg([r["score"] for r in responses]),
        "response_count": response_count,
        "sent_count":     sent_count,
        "participation":  participation,
        "by_dim":         by_dim,
    }


def detect_streak(current_week: int) -> int:
    streak = 0
    for w in range(current_week, current_week - STREAK_WEEKS - 1, -1):
        stats = get_stats(w)
        if stats and stats["avg_score"] <= ALERT_LOW:
            streak += 1
        else:
            break
    return streak


# ── Advice ─────────────────────────────────────────────────────────────────

DIM_ICON = {
    "mood":       "\U0001f60a",
    "energy":     "\u26a1",
    "workload":   "\U0001f4cb",
    "connection": "\U0001f91d",
    "clarity":    "\U0001f3af",
}

DIM_ADVICE = {
    "mood":       "Team morale is low. A light social touch \u2014 a non-work moment or informal chat \u2014 can help more than you'd expect.",
    "energy":     "The team is running on empty. Check for overwork patterns, late meetings, or unclear boundaries around off-hours.",
    "workload":   "Workload pressure is building. Review priorities together and protect at least one deep-focus block per day.",
    "connection": "The team feels isolated. Consider a virtual social event, pair-working session, or even a casual voice call.",
    "clarity":    "Direction is unclear. A short priorities sync this week would have outsized impact on everyone's confidence.",
}


# ── Schedule info ──────────────────────────────────────────────────────────

def print_schedule():
    log.info("=" * 44)
    log.info("MoodAnalyser \u2014 active alerts schedule")
    log.info("  Alerts cron : %s", SCHEDULE_ALERTS)
    log.info("=" * 44)


# ── Main ───────────────────────────────────────────────────────────────────

def run():
    db.bootstrap()
    print_schedule()

    current_week = utils.get_week_number()
    last_week    = current_week - 1
    prev_week    = current_week - 2

    this  = get_stats(last_week)
    prior = get_stats(prev_week)

    # ── Not enough data ────────────────────────────────────────────────
    if not this:
        send_to_manager(
            f"*MoodAnalyser \u2014 Weekly Report* \U0001f4ca\n\n"
            f"Hey! Woody here \ud83c\udf3f\n\n"
            f"Not enough responses yet to generate a report "
            f"(minimum {MIN_RESPONSES} needed). Keep it running!\n\n"
            f"_Schedule: {SCHEDULE_ALERTS}_\n"
            f"_\u2014 Woody \ud83c\udf3f_"
        )
        log.info("Not enough data for week %d.", last_week)
        return

    # ── Deltas ─────────────────────────────────────────────────────────
    delta     = round(this["avg_score"] - prior["avg_score"], 2) if prior else None
    delta_str = (
        (f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}")
        if delta is not None else "first week of data"
    )

    # ── Streak & flags ─────────────────────────────────────────────────
    streak      = detect_streak(last_week)
    is_dip      = delta is not None and delta <= ALERT_DELTA
    is_low      = this["avg_score"] <= ALERT_LOW
    is_streak   = streak >= STREAK_WEEKS
    is_low_p    = this["participation"] < PARTICIPATION_WARN
    needs_alert = is_dip or is_low or is_streak

    # ── Best / worst dimension ─────────────────────────────────────────
    scored_dims = [(d, v) for d, v in this["by_dim"].items() if v is not None]
    scored_dims.sort(key=lambda x: x[1])
    worst_dim = scored_dims[0][0]  if scored_dims else None
    best_dim  = scored_dims[-1][0] if scored_dims else None

    # ── Compose message ────────────────────────────────────────────────
    if is_streak:
        header = (
            "*MoodAnalyser \u2014 STREAK ALERT* \ud83d\udea8\n\n"
            "Woody here \ud83c\udf3f \u2014 I need to flag something serious.\n\n"
        )
    elif needs_alert:
        header = (
            "*MoodAnalyser \u2014 Attention Needed* \u26a0\ufe0f\n\n"
            "Woody here \ud83c\udf3f \u2014 a few things to flag this week.\n\n"
        )
    else:
        header = (
            "*MoodAnalyser \u2014 Weekly Report* \U0001f4ca\n\n"
            "Woody here \ud83c\udf3f \u2014 here's how the team did this week.\n\n"
        )

    msg  = header
    msg += f"*Week {last_week} summary*\n"
    msg += f"Overall: {score_bar(this['avg_score'])}"
    msg += f" ({delta_str} vs last week)\n\n" if delta is not None else "\n\n"

    msg += "*Dimension breakdown*\n"
    for dim in ["mood", "energy", "workload", "connection", "clarity"]:
        msg += f"{DIM_ICON[dim]} {dim.capitalize()}: {score_bar(this['by_dim'].get(dim))}\n"
    msg += "\n"

    msg += "*Participation rate*\n"
    msg += f"{rate_bar(this['participation'])}\n"
    msg += f"{this['response_count']} / {this['sent_count']} members responded\n\n"

    if is_streak:
        msg += (
            f"\ud83d\udea8 *{streak}-week streak below {ALERT_LOW}/3* \u2014 "
            f"this is sustained distress, not a blip. "
            f"Consider a 1:1 check-in or team retrospective.\n\n"
        )

    if needs_alert and worst_dim:
        msg += f"\ud83d\udccd *Lowest dimension: {worst_dim}*\n{DIM_ADVICE[worst_dim]}\n\n"

    if needs_alert and best_dim and best_dim != worst_dim:
        msg += (
            f"\u2705 *Strength this week: {best_dim}* \u2014 "
            f"whatever is working here, protect it.\n\n"
        )

    if is_low_p:
        msg += (
            f"\ud83d\udcc9 *Low participation ({this['participation'] * 100:.0f}%)* \u2014 "
            f"check if the pulse timing works for the team.\n\n"
        )

    msg += f"_Schedule: {SCHEDULE_ALERTS}_\n"
    msg += "_All data is aggregated anonymously. No individual responses are visible._\n"
    msg += "_\u2014 Woody \ud83c\udf3f_"

    send_to_manager(msg)
    log.info("Weekly report sent for week %d.", last_week)

    db.save_weekly_summary(
        week_num       = last_week,
        avg_score      = this["avg_score"],
        response_count = this["response_count"],
        sent_count     = this["sent_count"],
        participation  = this["participation"],
        streak         = streak,
    )


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MoodAnalyser weekly alert generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 alerts.py
  python3 alerts.py --show-schedule

Schedule env var (in .env):
  SCHEDULE_ALERTS  cron expression (demo default: "5 * * * *")

Production value:
  SCHEDULE_ALERTS=0 9 * * 1   (Monday 9am)
        """,
    )
    parser.add_argument(
        "--show-schedule",
        action="store_true",
        help="Print active cron schedule and exit",
    )
    args = parser.parse_args()

    if args.show_schedule:
        print_schedule()
    else:
        run()