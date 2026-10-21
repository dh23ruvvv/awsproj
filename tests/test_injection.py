"""
Security injection tests:
Verifies prompt injection safety, tool execution allowlisting, SQL injection protection,
and cross-session isolation.
"""

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from server.config import settings
from server.database import get_connection
from server.main import app
from server.tools.registry import default_registry


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "offline_responses.json"


@pytest.fixture
def fixtures():
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_prompt_injection_safety(tmp_path, monkeypatch, fixtures):
    """Ensure instructions attempting to delete data or override system instructions fail safely."""
    db_file = str(tmp_path / "sec_inject.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")

    with TestClient(app) as client:
        # Create seeded session
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]

        # Count tasks and blocks prior to attack
        db = get_connection()
        t_count_before = db.execute("SELECT count(*) FROM tasks WHERE session_id = ?", (sid,)).fetchone()[0]
        c_count_before = db.execute("SELECT count(*) FROM calendar_blocks WHERE session_id = ?", (sid,)).fetchone()[0]
        assert t_count_before > 0
        assert c_count_before > 0

        # Send injection attack
        attack_prompt = fixtures["injection_attempt_1"]["prompt"]
        res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": attack_prompt})
        assert res.status_code == 200
        data = res.json()

        # Verify no forbidden tools executed
        for tool_call in data["tool_trace"]:
            assert tool_call["tool"] not in fixtures["injection_attempt_1"]["forbidden_tools"]

        # Verify data untouched
        t_count_after = db.execute("SELECT count(*) FROM tasks WHERE session_id = ?", (sid,)).fetchone()[0]
        c_count_after = db.execute("SELECT count(*) FROM calendar_blocks WHERE session_id = ?", (sid,)).fetchone()[0]
        assert t_count_after == t_count_before
        assert c_count_after == c_count_before
        db.close()


def test_sql_injection_resistance(tmp_path, monkeypatch, fixtures):
    """Ensure raw SQL syntax within messages does not corrupt SQLite."""
    db_file = str(tmp_path / "sec_sql.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)

    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
        attack_prompt = fixtures["sql_injection_attempt"]["prompt"]

        res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": attack_prompt})
        assert res.status_code == 200

        # Verify sessions table still exists and row is intact
        db = get_connection()
        row = db.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
        assert row is not None
        assert row["id"] == sid
        db.close()


def test_tool_allowlist_enforcement():
    """Verify registry rejects unauthorized tools."""
    with pytest.raises(KeyError):
        default_registry.get("delete_all_data")

    with pytest.raises(KeyError):
        default_registry.get("execute_sql")


def test_session_isolation(tmp_path, monkeypatch):
    """Ensure data and proposals cannot be accessed or manipulated across sessions."""
    db_file = str(tmp_path / "sec_isolation.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)

    with TestClient(app) as client:
        sid_1 = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
        sid_2 = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]

        # Create plan in session 1
        t1_res = client.post(f"/api/v1/sessions/{sid_1}/agent/message", json={"message": "Plan my day"})
        plan_id = t1_res.json()["plan_id"]
        assert plan_id is not None

        # Attempt to confirm session 1's plan using session 2 -> must return 404
        bad_confirm = client.post(f"/api/v1/sessions/{sid_2}/plans/{plan_id}/confirm", json={"state_version": 1})
        assert bad_confirm.status_code == 404

        # Attempt to get session 1's plan using session 2 -> must return 404
        bad_get = client.get(f"/api/v1/sessions/{sid_2}/plans/{plan_id}")
        assert bad_get.status_code == 404
