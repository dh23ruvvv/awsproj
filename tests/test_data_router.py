"""Test session-scoped data retrieval endpoints per Architecture §5.4."""

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Start the test client with an isolated SQLite database."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "data.db"))
    with TestClient(app) as test_client:
        yield test_client


def test_data_retrieval_endpoints(client):
    """Verify schedule, tasks, memory, and execution-log endpoints."""
    # Seed session
    res = client.post("/api/v1/sessions", json={"seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30"})
    assert res.status_code == 201
    sid = res.json()["session_id"]

    # 1. GET /sessions/{sid}/schedule
    sched_res = client.get(f"/api/v1/sessions/{sid}/schedule")
    assert sched_res.status_code == 200
    sched_data = sched_res.json()
    assert "blocks" in sched_data
    assert sched_data["state_version"] == 1
    assert len(sched_data["blocks"]) == 2

    # 2. GET /sessions/{sid}/tasks
    tasks_res = client.get(f"/api/v1/sessions/{sid}/tasks")
    assert tasks_res.status_code == 200
    tasks_data = tasks_res.json()
    assert "tasks" in tasks_data
    assert tasks_data["state_version"] == 1
    assert len(tasks_data["tasks"]) == 5

    # 3. GET /sessions/{sid}/memory
    mem_res = client.get(f"/api/v1/sessions/{sid}/memory")
    assert mem_res.status_code == 200
    mem_data = mem_res.json()
    assert "entries" in mem_data
    assert mem_data["state_version"] == 1
    assert mem_data["entries"] == []

    # 4. GET /sessions/{sid}/execution-log
    log_res = client.get(f"/api/v1/sessions/{sid}/execution-log")
    assert log_res.status_code == 200
    log_data = log_res.json()
    assert "entries" in log_data

    # Unknown session -> 404
    for endpoint in ("schedule", "tasks", "memory", "execution-log"):
        not_found = client.get(f"/api/v1/sessions/unknown-id/{endpoint}")
        assert not_found.status_code == 404
        assert not_found.json()["error"]["code"] == "SESSION_NOT_FOUND"
