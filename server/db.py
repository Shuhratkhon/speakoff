"""SQLite database (one file: server/data/app.db). No extra server needed; fine for the first thousands of users."""

import sqlite3
import threading
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
DB_PATH = DATA / "app.db"
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash      TEXT NOT NULL,
    contact      TEXT NOT NULL UNIQUE,          -- email (lower case) or phone (+digits)
    contact_type TEXT NOT NULL,                 -- 'email' | 'phone'
    theme        TEXT NOT NULL DEFAULT 'dark',
    voice        TEXT NOT NULL DEFAULT 'female',
    lang         TEXT NOT NULL DEFAULT 'en',
    plan         TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'plus' | 'pro'
    plan_period  TEXT,                          -- 'monthly' | 'yearly'
    plan_renews  TEXT,                          -- ISO date
    bonus_left   INTEGER NOT NULL DEFAULT 3,    -- free welcome recordings
    created      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS codes (              -- sign-up codes sent by email / SMS
    contact      TEXT PRIMARY KEY,
    contact_type TEXT NOT NULL,
    code_hash    TEXT NOT NULL,
    expires      REAL NOT NULL,
    attempts     INTEGER NOT NULL DEFAULT 0,
    sent_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS recordings (
    id            TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode          TEXT NOT NULL,                -- 'audio' | 'video'
    sections      TEXT NOT NULL,                -- "fluency,grammar,..."
    question      TEXT,                         -- question of the day (or NULL)
    is_daily      INTEGER NOT NULL DEFAULT 0,
    used_bonus    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL,                -- queued | running | done | failed
    error         TEXT,
    created       TEXT NOT NULL,                -- ISO time (UTC)
    day           TEXT NOT NULL,                -- local date, for the daily limits
    duration      REAL,
    trimmed       INTEGER NOT NULL DEFAULT 0,
    src_path      TEXT,                         -- the upload (deleted after analysis)
    audio_path    TEXT,                         -- kept 14 / 30 / 90 days by plan
    audio_deleted INTEGER NOT NULL DEFAULT 0,
    data          TEXT,                         -- analysis (JSON)
    overall       INTEGER,
    cefr          TEXT,
    ielts         REAL,
    scores        TEXT                          -- JSON {fluency: .., grammar: .., ...}
);
CREATE INDEX IF NOT EXISTS rec_user ON recordings(user_id, created);

-- Ranked 1v1 (server/ranked.py)
CREATE TABLE IF NOT EXISTS ranked_queue (
    user_id   INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    rp        INTEGER NOT NULL,
    joined    REAL NOT NULL,
    last_poll REAL NOT NULL,
    match_id  TEXT
);
CREATE TABLE IF NOT EXISTS matches (
    id        TEXT PRIMARY KEY,
    season    TEXT NOT NULL,
    kind      TEXT NOT NULL,                    -- 'player' | 'ghost' (a real player's earlier answer) | 'bot'
    question  TEXT NOT NULL,
    created   REAL NOT NULL,
    reveal_at REAL NOT NULL,                    -- question shown
    speak_at  REAL NOT NULL,                    -- recording starts (5 s later)
    deadline  REAL NOT NULL,                    -- last moment an answer can arrive
    status    TEXT NOT NULL,                    -- 'live' | 'done'
    day       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS match_players (
    match_id  TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    slot      INTEGER NOT NULL,
    user_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,   -- NULL = bot (or a deleted account)
    is_ghost  INTEGER NOT NULL DEFAULT 0,       -- 1 = replay of an earlier answer (does not change that player)
    rp_before INTEGER NOT NULL DEFAULT 0,
    rp_delta  INTEGER,
    status    TEXT NOT NULL,                    -- waiting | uploaded | running | done | failed | missed
    error     TEXT,
    src_path  TEXT,
    audio_path TEXT,
    duration  REAL,
    overall   INTEGER,
    scores    TEXT,                             -- JSON {fluency, grammar, vocabulary, pronunciation}
    extras    TEXT,                             -- JSON {words, fillers, mistakes, b2, cefr}
    result    TEXT,                             -- 'win' | 'loss' | 'draw' | 'none'
    PRIMARY KEY (match_id, slot)
);
CREATE INDEX IF NOT EXISTS mp_user ON match_players(user_id);
CREATE TABLE IF NOT EXISTS friendships (        -- server/friends.py; accepted = a row each way
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status    TEXT NOT NULL,                    -- 'pending' (user_id asked friend_id) | 'accepted'
    created   REAL NOT NULL,
    PRIMARY KEY (user_id, friend_id)
);
CREATE TABLE IF NOT EXISTS challenges (         -- friendly 1v1 invitations
    id        TEXT PRIMARY KEY,
    from_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created   REAL NOT NULL,
    status    TEXT NOT NULL,                    -- pending | accepted | declined | cancelled | expired
    match_id  TEXT
);
CREATE TABLE IF NOT EXISTS daily_claims (       -- Speakoff credits collected from the Home calendar
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    streak_day INTEGER NOT NULL,                -- 1-7
    amount     INTEGER NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS skill_grants (       -- one skill per 20 ranked matches (server/rewards.py)
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    block     INTEGER NOT NULL,                 -- 1 = matches 1-20, 2 = matches 21-40, ...
    skill     TEXT NOT NULL,
    season    TEXT NOT NULL,
    earned    TEXT NOT NULL,
    PRIMARY KEY (user_id, block)
);
CREATE TABLE IF NOT EXISTS user_awards (        -- achievement tiers, award = "<id>:<tier 1-3>" (server/rewards.py)
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,                    -- 'skill' | 'ach'
    award     TEXT NOT NULL,
    earned    TEXT NOT NULL,
    PRIMARY KEY (user_id, kind, award)
);
"""

# columns added after the first version (added to an old database on start)
USER_COLUMNS = {
    "photo": "INTEGER NOT NULL DEFAULT 0",         # 1 = server/data/photos/<id>.jpg exists
    "frame": "TEXT NOT NULL DEFAULT 'none'",
    "shown_skills": "TEXT NOT NULL DEFAULT ''",    # up to 2 skill ids, comma separated
    "rp": "INTEGER NOT NULL DEFAULT 0",            # rank points (this season)
    "best_rp": "INTEGER NOT NULL DEFAULT 0",       # highest ever (unlocks rank frames)
    "season": "TEXT",
    "last_seen": "REAL",
    "country": "TEXT",
    "credits": "INTEGER NOT NULL DEFAULT 0",       # Speakoff credits (server/credits.py)
    "google_sub": "TEXT",                          # Sign in with Google (server/oauth.py)
    "apple_sub": "TEXT",                           # Sign in with Apple
    "has_password": "INTEGER NOT NULL DEFAULT 1",  # 0 = made with Google / Apple and no password set yet                             # ISO 3166 code (e.g. KR, UZ) for the national leaderboard                           # for "online" in the friends list
}


def conn():
    """One connection per thread."""
    c = getattr(_local, "conn", None)
    if c is None:
        DATA.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        _local.conn = c
    return c


def init():
    c = conn()
    c.executescript(SCHEMA)
    have = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
    for name, kind in USER_COLUMNS.items():
        if name not in have:
            c.execute(f"ALTER TABLE users ADD COLUMN {name} {kind}")
    # first version of skills / achievements (2026-11-23 morning): replaced by stacking skills and tiers
    c.execute("DELETE FROM user_awards WHERE kind='skill' OR award NOT LIKE '%:%'")
    c.commit()


def one(sql, *args):
    return conn().execute(sql, args).fetchone()


def all_(sql, *args):
    return conn().execute(sql, args).fetchall()


def run(sql, *args):
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur
