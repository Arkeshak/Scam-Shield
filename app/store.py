"""Tiny SQLite store for the family links. It saves NO message content - only who is linked to whom."""
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from . import config


def _conn():
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users(chat_id INTEGER PRIMARY KEY, name TEXT, language TEXT DEFAULT 'English')")
    conn.execute("CREATE TABLE IF NOT EXISTS links(elder_id INTEGER, guardian_id INTEGER, PRIMARY KEY(elder_id, guardian_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS invites(code TEXT PRIMARY KEY, elder_id INTEGER, created REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, elder_id INTEGER, risk TEXT, scam_type TEXT, ts REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS check_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, ts REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS join_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, ts REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS webcodes(code TEXT PRIMARY KEY, elder_id INTEGER, created REAL)")
    return conn


def upsert_user(chat_id: int, name: str):
    with _conn() as c:
        c.execute("INSERT INTO users(chat_id, name) VALUES(?, ?) ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name", (chat_id, name))


def get_name(chat_id: int) -> str:
    with _conn() as c:
        row = c.execute("SELECT name FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else "your family member"


def set_language(chat_id: int, language: str):
    with _conn() as c:
        c.execute("INSERT INTO users(chat_id, language) VALUES(?, ?) ON CONFLICT(chat_id) DO UPDATE SET language=excluded.language", (chat_id, language))


def get_language(chat_id: int) -> str:
    with _conn() as c:
        row = c.execute("SELECT language FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row[0] if row and row[0] else "English"


def create_invite(elder_id: int) -> str:
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM invites WHERE created < ?", (time.time() - 3600,))
        code = f"{secrets.randbelow(1_000_000):06d}"
        while c.execute("SELECT 1 FROM invites WHERE code=?", (code,)).fetchone():
            code = f"{secrets.randbelow(1_000_000):06d}"
        c.execute("INSERT OR REPLACE INTO invites(code, elder_id, created) VALUES(?, ?, ?)", (code, elder_id, time.time()))
    return code


def allow_join_attempt(chat_id: int, limit: int = 5, window_s: int = 3600) -> bool:
    now = time.time()
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM join_attempts WHERE ts < ?", (now - 86400,))
        count = c.execute(
            "SELECT COUNT(*) FROM join_attempts WHERE chat_id=? AND ts>=?",
            (chat_id, now - window_s),
        ).fetchone()[0]
        if count >= limit:
            return False
        c.execute("INSERT INTO join_attempts(chat_id, ts) VALUES(?, ?)", (chat_id, now))
        return True


def accept_invite(guardian_id: int, code: str, max_age_s: int = 3600):
    """Returns elder_id if the code is valid, else None."""
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT elder_id, created FROM invites WHERE code=?", (code.strip(),)).fetchone()
        if not row or time.time() - row[1] > max_age_s or row[0] == guardian_id:
            return None
        c.execute("INSERT OR IGNORE INTO links(elder_id, guardian_id) VALUES(?, ?)", (row[0], guardian_id))
        c.execute("DELETE FROM invites WHERE code=?", (code.strip(),))
        return row[0]


def get_guardians(elder_id: int) -> list[int]:
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT guardian_id FROM links WHERE elder_id=?", (elder_id,))]


def log_event(elder_id: int, risk: str, scam_type: str):
    with _conn() as c:
        c.execute("INSERT INTO events(elder_id, risk, scam_type, ts) VALUES(?, ?, ?, ?)", (elder_id, risk, scam_type, time.time()))


def consume_check_quota(chat_id: int, limit: int = 20, window_s: int = 3600) -> bool:
    now = time.time()
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM check_requests WHERE ts < ?", (now - 86400,))
        count = c.execute(
            "SELECT COUNT(*) FROM check_requests WHERE chat_id=? AND ts>=?",
            (chat_id, now - window_s),
        ).fetchone()[0]
        if count >= limit:
            return False
        c.execute("INSERT INTO check_requests(chat_id, ts) VALUES(?, ?)", (chat_id, now))
        return True


def get_checks_today(chat_id: int) -> int:
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM events WHERE elder_id=? AND ts>=?",
            (chat_id, midnight),
        ).fetchone()[0]


def create_web_code(elder_id: int) -> str:
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM webcodes WHERE created < ?", (time.time() - 86400,))
        code = f"{secrets.randbelow(1_000_000):06d}"
        while c.execute("SELECT 1 FROM webcodes WHERE code=?", (code,)).fetchone():
            code = f"{secrets.randbelow(1_000_000):06d}"
        c.execute("INSERT OR REPLACE INTO webcodes(code, elder_id, created) VALUES(?, ?, ?)", (code, elder_id, time.time()))
    return code


def resolve_web_code(code: str, max_age_s: int = 86400):
    """Returns elder_id if valid, else None."""
    with _conn() as c:
        row = c.execute("SELECT elder_id, created FROM webcodes WHERE code=?", (code.strip(),)).fetchone()
        if not row or time.time() - row[1] > max_age_s:
            return None
        return row[0]


def forget(chat_id: int):
    with _conn() as c:
        c.execute("DELETE FROM users WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM links WHERE elder_id=? OR guardian_id=?", (chat_id, chat_id))
        c.execute("DELETE FROM invites WHERE elder_id=?", (chat_id,))
        c.execute("DELETE FROM events WHERE elder_id=?", (chat_id,))
        c.execute("DELETE FROM check_requests WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM join_attempts WHERE chat_id=?", (chat_id,))
        c.execute("DELETE FROM webcodes WHERE elder_id=?", (chat_id,))

