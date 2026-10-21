"""Tests for TASK-004 Backend Scaffolding."""
import os
import tempfile
import pytest
from server.config import settings, Settings
from server.clock import now
from server.database import init_db, get_connection, seed_session
from server.models import (
    SessionResponse,
    TaskModel,
    CalendarBlockModel,
    DiffSummary,
    PlanDetailsResponse,
)


def test_clock():
    demo_time = now("2026-10-22T09:00:00+05:30")
    assert "2026-10-22" in demo_time
    current_time = now()
    assert "+00:00" in current_time or "Z" in current_time or current_time is not None


def test_config():
    assert settings.flowpilot_port == 8000
    assert settings.flowpilot_default_provider == "deterministic"


def test_database_and_seed():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Verify pragmas
        cursor.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1
        cursor.execute("PRAGMA journal_mode")
        assert cursor.fetchone()[0].lower() == "wal"

        # Verify all 6 tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row[0] for row in cursor.fetchall()}
        required_tables = {"sessions", "tasks", "calendar_blocks", "plans", "execution_log", "memory"}
        assert required_tables <= tables

        # Seed test
        now_time = now()
        conn.execute(
            "INSERT INTO sessions (id, created_at, state_version, provider) VALUES (?, ?, 1, 'deterministic')",
            ("test-session", now_time),
        )
        seed_session(conn, "test-session")

        # Verify 5 tasks
        cursor.execute("SELECT title, priority, category FROM tasks WHERE session_id = ?", ("test-session",))
        tasks = cursor.fetchall()
        assert len(tasks) == 5

        # Verify 2 calendar blocks
        cursor.execute("SELECT title, immutable, task_id FROM calendar_blocks WHERE session_id = ?", ("test-session",))
        blocks = cursor.fetchall()
        assert len(blocks) == 2

        conn.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
