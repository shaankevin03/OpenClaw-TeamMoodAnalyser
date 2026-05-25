"""
bot.py — MoodAnalyser Telegram bot handler

Runs as a persistent process. Listens for button taps (callback_query)
from team members and records their responses anonymously to SQLite.
Uses long-polling — no public webhook or server required.
Woody greets new members when they send /start.
"""

from dotenv import load_dotenv
load_dotenv()

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
log = logging.getLogger("moodanalyser.bot")

# ── Config ─────────────────────────────────────────────────────────────────

BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API       = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30


# ── Telegram helpers ───────────────────────────────────────────────────────

def answer_callback(callback_query_id: str, text: str):
    """Acknowledge button tap — clears the loading spinner."""
    requests.post(
        f"{TG_API}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )


def edit_message(chat_id: str, message_id: int, text: str):
    """
    Replace the original question message with a confirmation.
    Removes the inline keyboard so the member cannot tap twice.
    """
    requests.post(
        f"{TG_API}/editMessageText",
        json={
            "chat_id":    chat_id,
            "message_id": message_id,
            "text":       text,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )


def send_message(chat_id: str, text: str):
    requests.post(
        f"{TG_API}/sendMessage",
        json={
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )


# ── Handlers ───────────────────────────────────────────────────────────────

def handle_callback(update: dict):
    """Process a button tap — validate, anonymise, record, confirm."""
    cq      = update["callback_query"]
    cq_id   = cq["id"]
    chat_id = str(cq["message"]["chat"]["id"])
    msg_id  = cq["message"]["message_id"]
    user_id = str(cq["from"]["id"])

    # Parse payload
    try:
        payload     = json.loads(cq["data"])
        question_id = payload["q"]
        dimension   = payload["d"]
        score       = int(payload["s"])
        batch       = payload["b"]
        week_num    = int(payload["w"])
        sent_at     = int(payload["t"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log.warning("Bad callback payload from %s: %s", user_id, e)
        answer_callback(cq_id, "Something went wrong — please try again.")
        return

    # Anonymise
    aid = utils.anon_id(user_id)

    # Idempotency — only record the first tap per question per week
    if db.already_answered(aid, question_id, week_num):
        answer_callback(cq_id, "Already recorded — thanks!")
        return

    # Record
    db.record_response(
        anon_id     = aid,
        question_id = question_id,
        dimension   = dimension,
        score       = score,
        batch       = batch,
        week_num    = week_num,
        sent_at     = sent_at,
        answered_at = utils.now_ms(),
    )

    log.info(
        "Recorded Q%d [%s] score=%d week=%d",
        question_id, dimension, score, week_num,
    )

    # Confirm and remove buttons
    question_text = cq["message"]["text"].split("\n\n", 1)[-1]
    edit_message(
        chat_id,
        msg_id,
        (
            f"*MoodAnalyser* \u2705\n\n"
            f"Got it \u2014 Woody logged that anonymously \ud83c\udf3f\n\n"
            f"_{question_text}_"
        ),
    )
    answer_callback(cq_id, "Woody logged it — thanks!")


def handle_start(update: dict):
    """
    Woody welcomes a new member and gives them their chat ID.
    They send this to the admin to be added to MOODANALYSER_MEMBERS.
    """
    msg     = update["message"]
    chat_id = str(msg["chat"]["id"])
    name    = msg["from"].get("first_name", "there")

    log.info("New /start from chat_id=%s name=%s", chat_id, name)

    send_message(
        chat_id,
        (
            f"Hey {name}! I'm *Woody* \ud83c\udf3f from *MoodAnalyser*.\n\n"
            "I'll send you a quick anonymous pulse twice a week \u2014 "
            "Tuesday and Thursday.\n\n"
            "Your responses are completely anonymous. "
            "Only aggregated team trends are ever shared with your manager.\n\n"
            f"Your chat ID is:\n`{chat_id}`\n\n"
            "_Send this to your admin to get added to the pulse._\n\n"
            "_\u2014 Woody \ud83c\udf3f_"
        ),
    )


# ── Long-poll loop ─────────────────────────────────────────────────────────

def run():
    db.bootstrap()
    log.info("MoodAnalyser bot starting — Woody is listening \ud83c\udf3f")

    offset = None

    while True:
        try:
            params: dict = {
                "timeout":         POLL_TIMEOUT,
                "allowed_updates": ["message", "callback_query"],
            }
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(
                f"{TG_API}/getUpdates",
                params=params,
                timeout=POLL_TIMEOUT + 5,
            )
            resp.raise_for_status()
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                if "callback_query" in update:
                    handle_callback(update)
                elif "message" in update:
                    text = update["message"].get("text", "")
                    if text.startswith("/start"):
                        handle_start(update)

        except requests.RequestException as e:
            log.error("Telegram poll error: %s — retrying in 5s", e)
            time.sleep(5)
        except Exception as e:
            log.exception("Unexpected error: %s — retrying in 5s", e)
            time.sleep(5)


if __name__ == "__main__":
    run()