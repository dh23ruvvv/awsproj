"""SQLite schema, configured connections, and session-scoped demo seeding."""

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from server.clock import now
from server.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, state_version INTEGER NOT NULL DEFAULT 1, demo_timestamp TEXT, provider TEXT NOT NULL DEFAULT 'deterministic');
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, title TEXT NOT NULL, duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0), deadline TEXT, priority TEXT NOT NULL CHECK(priority IN ('HIGH','MEDIUM','LOW')), category TEXT NOT NULL CHECK(category IN ('work','personal','meeting')), status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','scheduled','completed','cancelled')), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calendar_blocks (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, title TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, immutable INTEGER NOT NULL DEFAULT 0, task_id TEXT REFERENCES tasks(id), status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','completed','cancelled')), plan_id TEXT REFERENCES plans(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK(status IN ('PROPOSED','CONFIRMED','EXECUTING','EXECUTED','FAILED','CANCELLED','STALE')), proposed_blocks TEXT NOT NULL, diff_summary TEXT, explanation TEXT, state_version_at_proposal INTEGER NOT NULL, provider_used TEXT NOT NULL, degraded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, confirmed_at TEXT, executed_at TEXT);
CREATE TABLE IF NOT EXISTS execution_log (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, plan_id TEXT REFERENCES plans(id), tool_name TEXT NOT NULL, tool_args TEXT NOT NULL, tool_result TEXT NOT NULL, duration_ms INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, key TEXT NOT NULL, value TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open configured SQLite; the caller must close the returned connection."""
    path = settings.flowpilot_db_path if db_path is None else db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        connection.close()
        raise
    return connection


def init_db(db_path: str | None = None) -> None:
    """Create the exact six-table schema without changing existing data."""
    connection = get_connection(db_path)
    try:
        connection.executescript(SCHEMA)
    finally:
        connection.close()


def seed_session(connection: sqlite3.Connection, session_id: str) -> None:
    """Seed an existing empty session atomically without committing caller work.

    Fixture labels map to UUIDs because task primary keys are global. A savepoint
    rolls back partial inserts. Missing or populated sessions raise ValueError.
    """
    seed = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    session = connection.execute(
        "SELECT demo_timestamp FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise ValueError("Session does not exist")
    if connection.execute(
        "SELECT 1 FROM tasks WHERE session_id = ? UNION ALL "
        "SELECT 1 FROM calendar_blocks WHERE session_id = ? LIMIT 1",
        (session_id, session_id),
    ).fetchone() is not None:
        raise ValueError("Session already contains tasks or calendar blocks")
    created_at = now(session["demo_timestamp"])
    task_ids = {task["id"]: str(uuid4()) for task in seed["tasks"]}
    connection.execute("SAVEPOINT seed_session")
    try:
        for task in seed["tasks"]:
            connection.execute(
                "INSERT INTO tasks (id, session_id, title, duration_minutes, deadline, "
                "priority, category, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task_ids[task["id"]], session_id, task["title"], task["duration_minutes"],
                 task["deadline"], task["priority"], task["category"], task["status"], created_at),
            )
        for block in seed["calendar_blocks"]:
            connection.execute(
                "INSERT INTO calendar_blocks (id, session_id, title, start_time, end_time, "
                "immutable, task_id, status, plan_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), session_id, block["title"], block["start_time"], block["end_time"],
                 block["immutable"], task_ids.get(block["task_id"]), block["status"], None, created_at),
            )
        connection.execute("RELEASE SAVEPOINT seed_session")
    except Exception:
        connection.execute("ROLLBACK TO SAVEPOINT seed_session")
        connection.execute("RELEASE SAVEPOINT seed_session")
        raise
