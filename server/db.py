"""SQLite 持久层。内容（知识点/题目）在内存中，这里只存学习状态。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "grammar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS card (
    kp_id        TEXT PRIMARY KEY,
    state        TEXT NOT NULL DEFAULT 'new',
    stability    REAL NOT NULL DEFAULT 0,
    difficulty   REAL NOT NULL DEFAULT 0,
    due_at       TEXT,
    last_review  TEXT,
    reps         INTEGER NOT NULL DEFAULT 0,
    lapses       INTEGER NOT NULL DEFAULT 0,
    leech        INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS review_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_id          TEXT NOT NULL,
    drill_id       TEXT,
    mode           TEXT NOT NULL,
    rating         INTEGER NOT NULL,
    correct        INTEGER NOT NULL,
    total          INTEGER NOT NULL DEFAULT 0,
    hits           INTEGER NOT NULL DEFAULT 0,
    latency_ms     INTEGER NOT NULL DEFAULT 0,
    prev_stability REAL,
    new_stability  REAL,
    interval_days  REAL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drill_stat (
    drill_id    TEXT PRIMARY KEY,
    kp_id       TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    last_seen   TEXT,
    last_correct INTEGER
);

CREATE TABLE IF NOT EXISTS error_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_id         TEXT NOT NULL,
    drill_id      TEXT NOT NULL,
    user_answer   TEXT,
    correct_answer TEXT,
    source        TEXT NOT NULL DEFAULT 'practice',
    resolved      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS day_stat (
    day      TEXT PRIMARY KEY,
    reviews  INTEGER NOT NULL DEFAULT 0,
    new_kp   INTEGER NOT NULL DEFAULT 0,
    correct  INTEGER NOT NULL DEFAULT 0,
    total    INTEGER NOT NULL DEFAULT 0,
    minutes  REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS session (
    id         TEXT PRIMARY KEY,
    mode       TEXT NOT NULL,
    config     TEXT,
    state      TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS exam (
    id           TEXT PRIMARY KEY,
    profile      TEXT NOT NULL,
    paper        TEXT NOT NULL,
    answers      TEXT,
    started_at   TEXT NOT NULL,
    submitted_at TEXT,
    result       TEXT
);

CREATE TABLE IF NOT EXISTS gen_drill (
    id         TEXT PRIMARY KEY,
    kp_id      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 「只复习概念」的阅读记录：只记看过什么，不参与 FSRS 排期
CREATE TABLE IF NOT EXISTS concept_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_id     TEXT NOT NULL,
    day       TEXT NOT NULL,
    viewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS setting (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_card_due ON card(due_at);
CREATE INDEX IF NOT EXISTS idx_log_kp ON review_log(kp_id);
CREATE INDEX IF NOT EXISTS idx_log_time ON review_log(created_at);
CREATE INDEX IF NOT EXISTS idx_err_kp ON error_log(kp_id);
CREATE INDEX IF NOT EXISTS idx_gen_kp ON gen_drill(kp_id);
CREATE INDEX IF NOT EXISTS idx_concept_kp ON concept_log(kp_id);
CREATE INDEX IF NOT EXISTS idx_concept_day ON concept_log(day);
"""

DEFAULT_SETTINGS = {
    "retention": "0.9",
    "new_per_day": "4",
    "review_per_day": "40",
    "learn_drills": "4",
    "review_drills": "3",
    "daily_goal": "30",
    "show_hint": "1",
    "prereq_gate": "0",
    "variant_mode": "mix",
    "concept_per_round": "8",
}


def now() -> datetime:
    """本地时间（不带时区），用于日期统计。"""
    return datetime.now().replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO setting(k, v) VALUES (?, ?)", (k, v))


def log_concept_view(kp_id: str) -> None:
    """记一次「读过讲解」。刻意不进 review_log，也不碰 card 的 S/D。"""
    ts = now()
    with db() as conn:
        conn.execute(
            "INSERT INTO concept_log(kp_id, day, viewed_at) VALUES (?, ?, ?)",
            (kp_id, ts.date().isoformat(), iso(ts)),
        )


def get_settings() -> dict:
    with db() as conn:
        rows = conn.execute("SELECT k, v FROM setting").fetchall()
    s = dict(DEFAULT_SETTINGS)
    s.update({r["k"]: r["v"] for r in rows})
    return {
        "retention": float(s["retention"]),
        "new_per_day": int(s["new_per_day"]),
        "review_per_day": int(s["review_per_day"]),
        "learn_drills": int(s["learn_drills"]),
        "review_drills": int(s["review_drills"]),
        "daily_goal": int(s["daily_goal"]),
        "show_hint": s["show_hint"] == "1",
        "prereq_gate": s["prereq_gate"] == "1",
        "variant_mode": s["variant_mode"] if s["variant_mode"] in ("off", "mix", "half", "only") else "mix",
        "concept_per_round": max(3, min(30, int(s["concept_per_round"]))),
    }


def save_settings(patch: dict) -> dict:
    with db() as conn:
        for k, v in patch.items():
            if isinstance(v, bool):
                v = "1" if v else "0"
            conn.execute("INSERT INTO setting(k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
    return get_settings()
