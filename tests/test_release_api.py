"""Release regressions for real task APIs and approval boundary integrity."""

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.tools.propose_tools import propose_schedule


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "release.db"))
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")
    with TestClient(app) as client:
        response = client.post("/api/v1/sessions", json={
            "seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30"})
        assert response.status_code == 201
        sid = response.json()["session_id"]
        yield client, sid, f"/api/v1/sessions/{sid}"


def domain(sid):
    db = get_connection()
    try:
        return {table: [dict(row) for row in db.execute(
            f"SELECT * FROM {table} WHERE {'id' if table == 'sessions' else 'session_id'}=? ORDER BY id", (sid,))]
            for table in ("sessions", "tasks", "calendar_blocks", "memory")}
    finally:
        db.close()


def make_proposal(client, base, version=1):
    response = client.post(f"{base}/agent/message", json={"message": "Plan my day", "state_version": version})
    assert response.status_code == 200, response.text
    assert response.json()["has_proposal"]
    return response.json()["plan_id"]


def test_task_create_edit_delete_versions_and_calendar_isolation(workspace):
    client, sid, base = workspace
    calendar = client.get(f"{base}/schedule").json()["blocks"]
    created = client.post(f"{base}/tasks", json={"state_version": 1, "title": "  Prepare presentation  ", "duration_minutes": 45})
    assert created.status_code == 201, created.text
    task = created.json()["task"]
    assert task["title"] == "Prepare presentation" and created.json()["state_version"] == 2
    edited = client.patch(f"{base}/tasks/{task['id']}", json={"state_version": 2, "duration_minutes": 60, "priority": "HIGH", "deadline": "2026-10-22T16:00:00+05:30"})
    assert edited.status_code == 200
    assert edited.json()["state_version"] == 3
    assert edited.json()["task"]["duration_minutes"] == 60
    deleted = client.request("DELETE", f"{base}/tasks/{task['id']}", json={"state_version": 3})
    assert deleted.status_code == 200 and deleted.json() == {"state_version": 4, "deleted": True}
    assert task["id"] not in {item["id"] for item in client.get(f"{base}/tasks").json()["tasks"]}
    assert client.get(f"{base}/schedule").json()["blocks"] == calendar


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_stale_task_mutations_are_atomic(workspace, method):
    client, sid, base = workspace
    task = next(item for item in client.get(f"{base}/tasks").json()["tasks"] if item["title"] == "Grocery shopping")
    before = domain(sid)
    path = f"{base}/tasks" + ("" if method == "POST" else f"/{task['id']}")
    payload = {"state_version": 9, "title": "Stale edit", "duration_minutes": 20}
    response = client.request(method, path, json=payload)
    assert response.status_code == 409
    assert domain(sid) == before


@pytest.mark.parametrize("field,value", [
    ("title", "   "), ("duration_minutes", 0), ("duration_minutes", 481),
    ("priority", "URGENT"), ("deadline", "2026-10-22T16:00:00"),
    ("deadline", "not-a-date"), ("duration_minutes", None), ("title", None),
])
def test_invalid_task_fields_do_not_mutate(workspace, field, value):
    client, sid, base = workspace
    task = next(item for item in client.get(f"{base}/tasks").json()["tasks"] if item["title"] == "Grocery shopping")
    before = domain(sid)
    response = client.patch(f"{base}/tasks/{task['id']}", json={"state_version": 1, field: value})
    assert response.status_code == 422
    assert domain(sid) == before


def test_edit_stales_reviewed_proposal_and_prevents_commit(workspace):
    client, sid, base = workspace
    pid = make_proposal(client, base)
    task = next(item for item in client.get(f"{base}/tasks").json()["tasks"] if item["title"] == "Grocery shopping")
    edited = client.patch(f"{base}/tasks/{task['id']}", json={"state_version": 1, "duration_minutes": 30})
    assert edited.status_code == 200
    assert client.get(f"{base}/plans/{pid}").json()["status"] == "STALE"
    before = domain(sid)
    confirmed = client.post(f"{base}/plans/{pid}/confirm", json={"state_version": 2})
    assert confirmed.status_code == 409
    assert domain(sid) == before


def test_stale_agent_request_creates_no_proposal(workspace):
    client, sid, base = workspace
    before = domain(sid)
    response = client.post(f"{base}/agent/message", json={"message": "Plan my day", "state_version": 20})
    assert response.status_code == 409
    assert domain(sid) == before
    db = get_connection()
    try:
        assert db.execute("SELECT COUNT(*) FROM plans WHERE session_id=?", (sid,)).fetchone()[0] == 0
    finally:
        db.close()


@pytest.mark.parametrize("fault", ["truncation", "deadline"])
def test_invalid_task_allocation_cannot_be_proposed(workspace, fault):
    client, sid, base = workspace
    before = domain(sid)
    db = get_connection()
    try:
        task = db.execute("SELECT * FROM tasks WHERE session_id=? AND title='Quarterly report draft'", (sid,)).fetchone()
        blocks = deepcopy(before["calendar_blocks"])
        blocks.append({"title": task["title"], "task_id": task["id"], "immutable": False,
                       "start_time": "2026-10-22T15:30:00+05:30",
                       "end_time": "2026-10-22T16:00:00+05:30" if fault == "truncation" else "2026-10-22T17:30:00+05:30"})
        with pytest.raises(ValueError, match="exactly|deadline"):
            propose_schedule(sid, {"blocks": blocks}, db)
        assert db.execute("SELECT COUNT(*) FROM plans WHERE session_id=?", (sid,)).fetchone()[0] == 0
    finally:
        db.close()
    assert domain(sid) == before


@pytest.mark.parametrize("fault", ["removed", "moved", "unlocked", "identity", "association"])
def test_tampered_protected_schedule_rejected_atomically_at_commit(workspace, fault):
    client, sid, base = workspace
    pid = make_proposal(client, base)
    proposed = client.get(f"{base}/plans/{pid}").json()["proposed_blocks"]
    lunch = next(item for item in proposed if item["title"] == "Lunch")
    if fault == "removed":
        proposed.remove(lunch)
    elif fault == "moved":
        lunch.update(start_time="2026-10-22T16:00:00+05:30", end_time="2026-10-22T17:00:00+05:30")
    elif fault == "unlocked":
        lunch["immutable"] = False
    elif fault == "identity":
        lunch["id"] = "replacement-fixed-block"
    else:
        standup = next(item for item in proposed if item["title"] == "Team standup")
        standup["task_id"] = None
    db = get_connection()
    try:
        with db:
            db.execute("UPDATE plans SET proposed_blocks=? WHERE id=?", (json.dumps(proposed), pid))
    finally:
        db.close()
    before = domain(sid)
    response = client.post(f"{base}/plans/{pid}/confirm", json={"state_version": 1})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "COMMIT_FAILED"
    assert domain(sid) == before
    plan = client.get(f"{base}/plans/{pid}").json()
    assert plan["status"] == "FAILED"


def test_scheduled_task_edits_do_not_change_calendar(workspace):
    client, sid, base = workspace
    task = next(item for item in client.get(f"{base}/tasks").json()["tasks"] if item["title"] == "Team standup")
    before = domain(sid)
    for method, payload in [("PATCH", {"state_version": 1, "duration_minutes": 15}), ("DELETE", {"state_version": 1})]:
        response = client.request(method, f"{base}/tasks/{task['id']}", json=payload)
        assert response.status_code == 409
        assert domain(sid) == before


def test_task_mutation_cannot_cross_session_boundary(workspace):
    client, sid, base = workspace
    other = client.post("/api/v1/sessions", json={"seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30"}).json()["session_id"]
    other_tasks = client.get(f"/api/v1/sessions/{other}/tasks").json()["tasks"]
    target = next(item for item in other_tasks if item["title"] == "Grocery shopping")
    before, other_before = domain(sid), domain(other)
    response = client.patch(f"{base}/tasks/{target['id']}", json={"state_version": 1, "title": "Changed"})
    assert response.status_code == 404
    assert domain(sid) == before and domain(other) == other_before
