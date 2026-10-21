"""Exercise agent turns through HTTP against an isolated SQLite database."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.providers.deterministic import PLAN_RESPONSE
from server.routers import agent


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Start the application with fresh database and rate-limit state."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "agent.db"))
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")
    monkeypatch.setattr(agent, "_message_times", {})
    with TestClient(app) as test_client:
        yield test_client


def create_session(client):
    """Create the seeded golden-demo session with a fixed clock."""
    response = client.post("/api/v1/sessions", json={
        "seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30",
    })
    assert response.status_code == 201
    return response.json()["session_id"]


def test_full_turn_one(client):
    """Persist a proposed plan through the provider's complete tool sequence."""
    sid = create_session(client)
    response = client.post(f"/api/v1/sessions/{sid}/agent/message", json={
        "message": "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting.",
        "state_version": 1,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == PLAN_RESPONSE
    assert body["has_proposal"] is True
    assert UUID(body["plan_id"]).version == 4
    assert body["state_version"] == 1
    assert body["provider_used"] == "deterministic"
    assert body["degraded"] is False
    assert [item["tool"] for item in body["tool_trace"]] == [
        "get_tasks", "get_calendar", "get_current_time", "propose_schedule",
    ]
    connection = get_connection()
    try:
        plan = connection.execute(
            "SELECT status FROM plans WHERE id = ? AND session_id = ?",
            (body["plan_id"], sid),
        ).fetchone()
        assert plan["status"] == "PROPOSED"
        assert connection.execute(
            "SELECT COUNT(*) FROM calendar_blocks WHERE session_id = ?", (sid,)
        ).fetchone()[0] == 2
    finally:
        connection.close()


def test_rate_limit_boundary(client, monkeypatch):
    """Allow ten turns, isolate sessions, and expire timestamps at sixty seconds."""
    monkeypatch.setattr(agent, "monotonic", lambda: 100.0)
    sid = create_session(client)
    url = f"/api/v1/sessions/{sid}/agent/message"
    for _ in range(10):
        assert client.post(url, json={"message": "hello"}).status_code == 200
    monkeypatch.setattr(agent, "monotonic", lambda: 159.999)
    response = client.post(url, json={"message": "hello"})
    assert response.status_code == 429
    assert response.json() == {"error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded. Maximum 10 messages per minute per session.",
        "details": {},
    }}
    other = create_session(client)
    assert client.post(f"/api/v1/sessions/{other}/agent/message", json={"message": "hello"}).status_code == 200
    monkeypatch.setattr(agent, "monotonic", lambda: 160.0)
    assert client.post(url, json={"message": "hello"}).status_code == 200


def test_unknown_session(client):
    """Reject unknown sessions before invoking the provider or rate limiter."""
    sid = str(uuid4())
    response = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "hello"})
    assert response.status_code == 404
    assert response.json() == {"error": {
        "code": "SESSION_NOT_FOUND", "message": "Session not found", "details": {},
    }}
    assert sid not in agent._message_times


@pytest.mark.parametrize("message", ["", "x" * 1001])
def test_message_length_validation(client, message):
    """Reject utterances outside the documented size bounds."""
    sid = create_session(client)
    assert client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": message}).status_code == 422


def test_optional_version_and_current_state(client):
    """Accept null or omitted versions and return the authoritative DB version."""
    sid = create_session(client)
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE sessions SET state_version = ? WHERE id = ?", (7, sid))
    finally:
        connection.close()
    for extra in ({}, {"state_version": None}, {"state_version": 1}):
        response = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "hello", **extra})
        assert response.status_code == 200
        assert response.json()["state_version"] == 7
        assert response.json()["has_proposal"] is False
        assert response.json()["plan_id"] is None
