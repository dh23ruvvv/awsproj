"""Verify session endpoints against an isolated, real SQLite database."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.routers import sessions


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Run application startup with a temporary database and fresh limiter."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "sessions.db"))
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")
    monkeypatch.setattr(sessions, "_last_reset", {})
    with TestClient(app) as test_client:
        yield test_client


def rows(table, sid):
    """Read a session's persisted rows from a fixed allowlist of test tables."""
    assert table in {"sessions", "tasks", "calendar_blocks", "plans", "execution_log", "memory"}
    connection = get_connection()
    try:
        column = "id" if table == "sessions" else "session_id"
        return [dict(row) for row in connection.execute(
            f"SELECT * FROM {table} WHERE {column} = ?", (sid,)
        )]
    finally:
        connection.close()


def assert_seeded(sid):
    """Compare persisted demo fields and task links with the seed fixture."""
    seed = json.loads((Path(__file__).parents[1] / "server" / "seed.json").read_text(encoding="utf-8"))
    tasks = rows("tasks", sid)
    blocks = rows("calendar_blocks", sid)
    assert len(tasks) == len(seed["tasks"])
    assert len(blocks) == len(seed["calendar_blocks"])
    task_ids = {}
    for expected in seed["tasks"]:
        actual = next(task for task in tasks if task["title"] == expected["title"])
        assert {key: actual[key] for key in expected if key != "id"} == {
            key: value for key, value in expected.items() if key != "id"
        }
        task_ids[expected["id"]] = actual["id"]
    for expected in seed["calendar_blocks"]:
        actual = next(block for block in blocks if block["title"] == expected["title"])
        for key, value in expected.items():
            if key not in {"id", "task_id"}:
                assert actual[key] == value
        assert actual["task_id"] == task_ids.get(expected["task_id"])


@pytest.mark.parametrize("seed", [False, True])
def test_create_session(client, seed):
    """Create UUID4 sessions with optional seeding and a stored clock override."""
    timestamp = "2026-10-22T09:00:00+05:30"
    response = client.post("/api/v1/sessions", json={"seed": seed, "demo_timestamp": timestamp})
    assert response.status_code == 201
    body = response.json()
    sid = body["session_id"]
    assert UUID(sid).version == 4
    assert body == dict(session_id=sid, state_version=1, provider="deterministic", seeded=seed)
    assert rows("sessions", sid)[0]["demo_timestamp"] == timestamp
    if seed:
        assert_seeded(sid)
    else:
        assert rows("tasks", sid) == rows("calendar_blocks", sid) == []


def test_reset_clears_state_and_preserves_other_session(client):
    """Reset populated dependent tables without changing another session."""
    sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
    other = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
    snapshot = {table: rows(table, other) for table in ("sessions", "tasks", "calendar_blocks")}
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE sessions SET state_version = ? WHERE id = ?", (7, sid))
            connection.execute(
                "INSERT INTO plans (id, session_id, proposed_blocks, state_version_at_proposal, provider_used, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", ("plan", sid, "[]", 7, "deterministic", "now"),
            )
            connection.execute("UPDATE calendar_blocks SET plan_id = ? WHERE session_id = ?", ("plan", sid))
            connection.execute(
                "INSERT INTO execution_log (id, session_id, plan_id, tool_name, tool_args, tool_result, duration_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("log", sid, "plan", "test", "{}", "{}", 0, "now"),
            )
            connection.execute("INSERT INTO memory VALUES (?, ?, ?, ?, ?)", ("memory", sid, "key", "value", "now"))
    finally:
        connection.close()
    response = client.delete(f"/api/v1/sessions/{sid}")
    assert response.status_code == 200
    assert response.json() == {"reset": True, "state_version": 1}
    assert rows("sessions", sid)[0]["state_version"] == 1
    assert_seeded(sid)
    for table in ("plans", "execution_log", "memory"):
        assert rows(table, sid) == []
    for table, expected in snapshot.items():
        assert rows(table, other) == expected


def test_reset_rate_limit_boundary(client, monkeypatch):
    """Reject early repeats, allow exactly five seconds, and isolate limits."""
    monkeypatch.setattr(sessions, "monotonic", lambda: 100.0)
    sid = client.post("/api/v1/sessions", json={"seed": False}).json()["session_id"]
    assert client.delete(f"/api/v1/sessions/{sid}").status_code == 200
    assert_seeded(sid)
    monkeypatch.setattr(sessions, "monotonic", lambda: 104.999)
    response = client.delete(f"/api/v1/sessions/{sid}")
    assert response.status_code == 429
    assert response.json() == {"error": {"code": "RATE_LIMITED", "message": "Reset rate limit exceeded. Please wait 5 seconds.", "details": {}}}
    other = client.post("/api/v1/sessions", json={"seed": False}).json()["session_id"]
    assert client.delete(f"/api/v1/sessions/{other}").status_code == 200
    monkeypatch.setattr(sessions, "monotonic", lambda: 105.0)
    assert client.delete(f"/api/v1/sessions/{sid}").status_code == 200


def test_missing_session(client):
    """Return an unwrapped error envelope without creating an unknown session."""
    response = client.delete("/api/v1/sessions/unknown")
    assert response.status_code == 404
    assert "error" in response.json()
    assert rows("sessions", "unknown") == []


def test_failed_reset_rolls_back(client, monkeypatch):
    """Preserve all data and the reset allowance if re-seeding fails."""
    sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
    original = {table: rows(table, sid) for table in ("sessions", "tasks", "calendar_blocks")}

    def fail_seed(connection, session_id):
        """Simulate a failure inside the reset transaction."""
        raise RuntimeError("seed failed")

    with monkeypatch.context() as patch:
        patch.setattr(sessions, "seed_session", fail_seed)
        with pytest.raises(RuntimeError, match="seed failed"):
            client.delete(f"/api/v1/sessions/{sid}")
    for table, expected in original.items():
        assert rows(table, sid) == expected
    assert client.delete(f"/api/v1/sessions/{sid}").status_code == 200
