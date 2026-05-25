"""
skill.py — MoodAnalyser pulse sender

Reads questions.json and sends the correct batch to every team member
via Telegram inline keyboard buttons. Woody introduces each pulse.

Schedule is configurable via environment variables (set in .env):
  SCHEDULE_TUESDAY   cron for Tuesday batch   (default: "1 * * * *")
  SCHEDULE_THURSDAY  cron for Thursday batch  (default: "2 * * * *")

Production values:
  SCHEDULE_TUESDAY=0 10 * * 2
  SCHEDULE_THURSDAY=0 10 * * 4
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import logging
import os
import time

import requests

import db
import utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("moodanalyser.skill")

# ── Config ─────────────────────────────────────────────────────────────────

BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
MEMBER_IDS = [
    m.strip()
    for m in os.environ["MOODANALYSER_MEMBERS"].split(",")
    if m.strip()
]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SCHEDULE_TUESDAY  = os.environ.get("SCHEDULE_TUESDAY",  "1 * * * *")
SCHEDULE_THURSDAY = os.environ.get("SCHEDULE_THURSDAY", "2 * * * *")

# ── Woody's pulse intros ───────────────────────────────────────────────────
# One intro per batch — Woody greets the team differently each day.

WOODY_INTRO = {
    "tuesday": (
        "*MoodAnalyser* \ud83c\udf3f\n\n"
        "Hey! Woody here \ud83c\udf3f\n"
        "Quick Tuesday pulse \u2014 tap your answer, it's anonymous.\n\n"
    ),
    "thursday": (
        "*MoodAnalyser* \ud83c\udf3f\n\n"
        "Woody again \ud83c\udf3f\n"
        "Nearly the weekend \u2014 one quick question before you get there.\n\n"
    ),
}


# ── Telegram helpers ───────────────────────────────────────────────────────

def send_message(chat_id: str, text: str, reply_markup: dict) -> bool:
    """Send a Telegram message with an inline keyboard."""
    try:
        resp = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id":      chat_id,
                "text":         text,
                "parse_mode":   "Markdown",
                "reply_markup": json.dumps(reply_markup),
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Failed to send message to %s: %s", chat_id, e)
        return False


def build_keyboard(
    question: dict,
    week_num: int,
    sent_at: int,
    batch: str,
) -> dict:
    """
    Build a Telegram inline keyboard for a single question.
    Each button carries a compact JSON payload (Telegram limit: 64 bytes).
    """
    buttons = []
    for opt in question["options"]:
        payload = json.dumps(
            {
                "q": question["id"],
                "d": question["dimension"],
                "s": opt["score"],
                "b": batch,
                "w": week_num,
                "t": sent_at,
            },
            separators=(",", ":"),
        )
        buttons.append({"text": opt["label"], "callback_data": payload})

    return {"inline_keyboard": [buttons]}


# ── Schedule info ──────────────────────────────────────────────────────────

def print_schedule():
    log.info("=" * 44)
    log.info("MoodAnalyser — active pulse schedule")
    log.info("  Tuesday  batch : %s", SCHEDULE_TUESDAY)
    log.info("  Thursday batch : %s", SCHEDULE_THURSDAY)
    log.info("=" * 44)


# ── Main ───────────────────────────────────────────────────────────────────

def run(batch: str | None = None):
    """
    Send the pulse. Called by OpenClaw on schedule, or manually for testing.
    Pass batch='tuesday' or 'thursday' to override day-of-week detection.
    """
    db.bootstrap()
    print_schedule()

    resolved_batch = batch or utils.get_batch_for_today()
    questions      = utils.load_questions(resolved_batch)
    week_num       = utils.get_week_number()
    sent_at        = utils.now_ms()
    intro          = WOODY_INTRO[resolved_batch]

    log.info(
        "Sending %s batch (%d questions) to %d members — week %d",
        resolved_batch, len(questions), len(MEMBER_IDS), week_num,
    )

    for chat_id in MEMBER_IDS:
        aid = utils.anon_id(chat_id)
        db.upsert_member(aid)

        for question in questions:
            db.log_sent(aid, question["id"], resolved_batch, week_num)

            keyboard = build_keyboard(question, week_num, sent_at, resolved_batch)
            text     = f"{intro}{question['text']}"
            success  = send_message(chat_id, text, keyboard)

            if success:
                log.info(
                    "  Sent Q%d [%s] to member",
                    question["id"], question["dimension"],
                )
            else:
                log.warning("  Failed to send Q%d to member", question["id"])

            time.sleep(0.3)

    log.info("Pulse send complete.")


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MoodAnalyser pulse sender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 skill.py --dry-run
  python3 skill.py --dry-run --batch thursday
  python3 skill.py --batch tuesday
  python3 skill.py --show-schedule

Schedule env vars (in .env):
  SCHEDULE_TUESDAY   cron for Tuesday batch   (demo default: "1 * * * *")
  SCHEDULE_THURSDAY  cron for Thursday batch  (demo default: "2 * * * *")
        """,
    )
    parser.add_argument(
        "--batch",
        choices=["tuesday", "thursday"],
        help="Override day detection",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print questions without sending any Telegram messages",
    )
    parser.add_argument(
        "--show-schedule",
        action="store_true",
        help="Print active cron schedule and exit",
    )
    args = parser.parse_args()

    if args.show_schedule:
        print_schedule()

    elif args.dry_run:
        resolved  = args.batch or utils.get_batch_for_today()
        questions = utils.load_questions(resolved)
        print(f"\nDRY RUN — MoodAnalyser — {resolved} batch ({len(questions)} questions)")
        print(f"  Schedule tuesday  : {SCHEDULE_TUESDAY}")
        print(f"  Schedule thursday : {SCHEDULE_THURSDAY}")
        print(f"\n  Woody's intro:\n  {WOODY_INTRO[resolved].strip()}\n")
        for q in questions:
            print(f"  Q{q['id']} [{q['dimension']}]  {q['text']}")
            for opt in q["options"]:
                print(f"    [{opt['score']}] {opt['label']}")
        print()

    else:
        run(batch=args.batch)