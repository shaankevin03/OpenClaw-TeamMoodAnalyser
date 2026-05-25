"""
utils.py — MoodAnalyser shared utilities
Week number, anonymisation, question loading, and batch detection.
"""

from dotenv import load_dotenv
load_dotenv()

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Batch = Literal["tuesday", "thursday"]


def anon_id(telegram_user_id: str | int) -> str:
    """
    One-way SHA-256 hash of the Telegram user ID + private salt.
    The salt must never change after first deployment.
    """
    salt = os.environ["MOODANALYSER_SALT"]
    raw  = f"{telegram_user_id}{salt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_week_number() -> int:
    """ISO week number (1-53). Consistent across the whole team."""
    return datetime.now(timezone.utc).isocalendar().week


def get_batch_for_today() -> Batch:
    """
    Returns 'thursday' on Thursdays (weekday==3),
    'tuesday' on all other days.
    """
    return "thursday" if datetime.now(timezone.utc).weekday() == 3 else "tuesday"


def load_questions(batch: Batch) -> list[dict]:
    """
    Loads questions.json from the same directory as this file
    and returns only the questions for the requested batch.
    """
    path = Path(__file__).parent / "questions.json"
    with open(path, encoding="utf-8") as f:
        bank = json.load(f)
    return bank["batches"][batch]


def now_ms() -> int:
    """Current time as Unix milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)