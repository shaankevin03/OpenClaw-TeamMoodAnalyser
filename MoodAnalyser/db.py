"""
db.py — MoodAnalyser database layer
All SQLite interactions live here. No other file touches the DB directly.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get(
    "MOODANALYSER_DB",
    os.path.expanduser("~/.openclaw/moodanalyser.db")
)


@contextmanager
def get_conn():
    """Yields a connection and commits or rolls back cleanly."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bootstrap():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                anon_id   TEXT    PRIMARY KEY,
                joined_at INTEGER DEFAULT (strftime('%s','now') * 1000)
            );

            CREATE TABLE IF NOT EXISTS pulses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                anon_id     TEXT    NOT NULL,
                question_id INTEGER NOT NULL,
                dimension   TEXT    NOT NULL,
                score       INTEGER NOT NULL CHECK(score IN (1,2,3)),
                batch       TEXT    NOT NULL,
                week_num    INTEGER NOT NULL,
                sent_at     INTEGER NOT NULL,
                answered_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS sent_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                anon_id     TEXT    NOT NULL,
                question_id INTEGER NOT NULL,
                batch       TEXT    NOT NULL,
                week_num    INTEGER NOT NULL,
                sent_at     INTEGER DEFAULT (strftime('%s','now') * 1000)
            );

            CREATE TABLE IF NOT EXISTS weekly_summaries (
                week_num       INTEGER PRIMARY KEY,
                avg_score      REAL,
                response_count INTEGER,
                sent_count     INTEGER,
                participation  REAL,
                streak         INTEGER,
                created_at     INTEGER DEFAULT (strftime('%s','now') * 1000)
            );
        """)


def upsert_member(anon_id: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO members (anon_id) VALUES (?)",
            (anon_id,)
        )


def log_sent(anon_id: str, question_id: int, batch: str, week_num: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sent_log (anon_id, question_id, batch, week_num)
               VALUES (?, ?, ?, ?)""",
            (anon_id, question_id, batch, week_num)
        )


def already_answered(anon_id: str, question_id: int, week_num: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id FROM pulses
               WHERE anon_id=? AND question_id=? AND week_num=?""",
            (anon_id, question_id, week_num)
        ).fetchone()
        return row is not None


def record_response(
    anon_id: str,
    question_id: int,
    dimension: str,
    score: int,
    batch: str,
    week_num: int,
    sent_at: int,
    answered_at: int,
):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO pulses
                 (anon_id, question_id, dimension, score, batch,
                  week_num, sent_at, answered_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (anon_id, question_id, dimension, score, batch,
             week_num, sent_at, answered_at)
        )


def get_week_responses(week_num: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT dimension, score FROM pulses WHERE week_num=?",
            (week_num,)
        ).fetchall()


def get_sent_count(week_num: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM sent_log WHERE week_num=?",
            (week_num,)
        ).fetchone()
        return row["cnt"] if row else 0


def get_week_avg(week_num: int) -> Optional[float]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(score) as avg FROM pulses WHERE week_num=?",
            (week_num,)
        ).fetchone()
        return round(row["avg"], 2) if row and row["avg"] is not None else None


def save_weekly_summary(
    week_num: int,
    avg_score: float,
    response_count: int,
    sent_count: int,
    participation: float,
    streak: int,
):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO weekly_summaries
                 (week_num, avg_score, response_count,
                  sent_count, participation, streak)
               VALUES (?,?,?,?,?,?)""",
            (week_num, avg_score, response_count,
             sent_count, participation, streak)
        )