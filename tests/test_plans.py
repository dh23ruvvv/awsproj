"""Verify plan lifecycle, atomic persistence, isolation, and commit failures."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.tools.registry import default_registry
from server.tools.propose_tools import propose_schedule


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    """Create a seeded session and a real computed proposal."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "plans.db"))
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={
            "seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30",
        }).json()["session_id"]
        db = get_connection()
        try:
            pid = propose_schedule(sid, {"blocks": [], "explanation": "Plan focus time"}, db)["plan_id"]
        finally:
            db.close()
        yield client, sid, pid


def rows(table, sid):
    """Read persisted rows from an allowlisted table."""
    assert table in {"sessions", "tasks", "calendar_blocks", "plans", "memory", "execution_log"}
    db = get_connection()
    try:
        column = "id" if table == "sessions" else "session_id"
        return [dict(row) for row in db.execute(f"SELECT * FROM {table} WHERE {column}=?", (sid,))]
    finally:
        db.close()


def mutate(sql, args=()):
    """Commit a test setup mutation on its own connection."""
    db = get_connection()
    try:
        with db:
            db.execute(sql, args)
    finally:
        db.close()


def url(sid, pid):
    """Build the plan lifecycle URL."""
    return f"/api/v1/sessions/{sid}/plans/{pid}"


def snapshot(sid):
    """Capture all domain rows for atomicity and idempotency assertions."""
    return {table: rows(table, sid) for table in ("sessions", "tasks", "calendar_blocks", "memory")}


def test_details(scenario):
    """Expose decoded proposal metadata without writing state."""
    client, sid, pid = scenario
    plan = rows("plans", sid)[0]
    response = client.get(url(sid, pid))
    assert response.status_code == 200
    assert response.json() == dict(
        plan_id=pid, status="PROPOSED", proposed_blocks=json.loads(plan["proposed_blocks"]),
        diff=json.loads(plan["diff_summary"]), explanation="Plan focus time",
        state_version_at_proposal=1, provider_used="deterministic", degraded=False)


def test_confirm_and_idempotency(scenario):
    """Persist blocks, tasks, memory and timestamps through every transition."""
    client, sid, pid = scenario
    mutate("CREATE TABLE observed (status TEXT)")
    mutate("CREATE TRIGGER observe_status AFTER UPDATE OF status ON plans BEGIN INSERT INTO observed VALUES (NEW.status); END")
    response = client.post(url(sid, pid) + "/confirm", json={"state_version": 1})
    assert response.status_code == 200
    assert response.json()["state_version"] == 2
    assert response.json()["execution_log"][0]["tool_name"] == "commit_schedule"
    plan = rows("plans", sid)[0]
    assert plan["status"] == "EXECUTED"
    assert plan["confirmed_at"] == plan["executed_at"] == "2026-10-22T09:00:00+05:30"
    db = get_connection()
    try:
        assert [row[0] for row in db.execute("SELECT status FROM observed")] == ["CONFIRMED", "EXECUTING", "EXECUTED"]
    finally:
        db.close()
    proposed = json.loads(plan["proposed_blocks"])
    actual = rows("calendar_blocks", sid)
    assert len(actual) == len(proposed)
    for block in proposed:
        stored = next(b for b in actual if b["start_time"] == block["start_time"])
        for key in ("title", "start_time", "end_time", "task_id"):
            assert stored[key] == block.get(key)
        assert stored["plan_id"] == pid
    linked = {b["task_id"] for b in actual if b["task_id"]}
    assert all(t["status"] == "scheduled" for t in rows("tasks", sid) if t["id"] in linked)
    assert rows("memory", sid) == []
    before = snapshot(sid)
    logs = rows("execution_log", sid)
    repeat = client.post(url(sid, pid) + "/confirm", json={"state_version": 1})
    assert repeat.json() == {"committed": True, "state_version": 2, "already_executed": True}
    assert snapshot(sid) == before
    assert rows("execution_log", sid) == logs


@pytest.mark.parametrize("body", [{}, None])
def test_optional_version(scenario, body):
    """Confirm using the proposal snapshot with an empty or absent body."""
    client, sid, pid = scenario
    response = client.post(url(sid, pid) + "/confirm", **({} if body is None else {"json": body}))
    assert response.status_code == 200


@pytest.mark.parametrize("current,requested", [(1, 9), (2, 1), (2, 2)])
def test_stale(scenario, current, requested):
    """Reject wrong request versions and stale snapshots even with a fresh request."""
    client, sid, pid = scenario
    mutate("UPDATE sessions SET state_version=? WHERE id=?", (current, sid))
    before = snapshot(sid)
    response = client.post(url(sid, pid) + "/confirm", json={"state_version": requested})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_PLAN"
    assert response.json()["error"]["details"] == {"expected": 1, "current": current}
    assert rows("plans", sid)[0]["status"] == "STALE"
    assert snapshot(sid) == before


def test_cancel(scenario):
    """Cancellation transitions once, conflicts on retry, and prevents confirmation."""
    client, sid, pid = scenario
    before = snapshot(sid)
    assert client.post(url(sid, pid) + "/cancel").json() == {"cancelled": True, "state_version": 1}
    assert client.post(url(sid, pid) + "/cancel").status_code == 409
    assert rows("plans", sid)[0]["status"] == "CANCELLED"
    response = client.post(url(sid, pid) + "/confirm", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_PLAN_STATE"
    assert snapshot(sid) == before


@pytest.mark.parametrize("suffix", ["", "/confirm", "/cancel"])
@pytest.mark.parametrize("foreign", [False, True])
def test_missing_and_foreign(scenario, suffix, foreign):
    """All endpoints hide missing plans and plans belonging to another session."""
    client, sid, pid = scenario
    path = url("other" if foreign else sid, pid if foreign else "missing") + suffix
    response = client.get(path) if not suffix else client.post(path, json={})
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "PLAN_NOT_FOUND", "message": "Plan not found", "details": {}}}


def test_failed_commit(scenario):
    """A late failure rolls back blocks, tasks, memory, timestamps and version."""
    client, sid, pid = scenario
    mutate("CREATE TRIGGER reject_version BEFORE UPDATE OF state_version ON sessions BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
    before = snapshot(sid)
    response = client.post(url(sid, pid) + "/confirm", json={})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "COMMIT_FAILED"
    assert snapshot(sid) == before
    plan = rows("plans", sid)[0]
    assert plan["status"] == "FAILED"
    assert plan["confirmed_at"] is None and plan["executed_at"] is None
    log = rows("execution_log", sid)[-1]
    assert log["tool_name"] == "commit_schedule"
    assert json.loads(log["tool_result"]) == {"committed": False, "error": "forced failure"}


def test_tool_and_memory_replacement(scenario):
    """Registered commits work directly and replace a session's same-key memory."""
    client, sid, pid = scenario
    handler = default_registry.get("commit_schedule").handler
    for index in range(2):
        db = get_connection()
        try:
            if index:
                existing = [dict(row) for row in db.execute("SELECT * FROM calendar_blocks WHERE session_id=?", (sid,))]
                pid = propose_schedule(sid, {"blocks": existing, "explanation": "Manager 1-on-1"}, db)["plan_id"]
            else:
                db.execute("UPDATE plans SET explanation='Manager meeting' WHERE id=?", (pid,))
                db.commit()
            assert handler(sid, {"plan_id": pid}, db)["state_version"] == index + 2
        finally:
            db.close()
    memory = rows("memory", sid)
    assert memory == []  # Calendar titles are not evidence of user preferences.


def test_completed_and_dropped(scenario):
    """Keep completed rows and remove dropped mutable rows."""
    client, sid, pid = scenario
    original = rows("calendar_blocks", sid)
    mutate("UPDATE calendar_blocks SET status='completed' WHERE id=?", (original[0]["id"],))
    completed = rows("calendar_blocks", sid)[0]
    mutate("UPDATE plans SET proposed_blocks='[]' WHERE id=?", (pid,))
    before = snapshot(sid)
    assert client.post(url(sid, pid) + "/confirm", json={}).status_code == 500
    assert snapshot(sid) == before


@pytest.mark.parametrize("reference", ["task_id", "id"])
def test_foreign_block_references(scenario, reference):
    """A plan cannot change another session's tasks or calendar blocks."""
    client, sid, pid = scenario
    other = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
    foreign = rows("tasks" if reference == "task_id" else "calendar_blocks", other)[0]["id"]
    block = json.loads(rows("plans", sid)[0]["proposed_blocks"])[0]
    block[reference] = foreign
    mutate("UPDATE plans SET proposed_blocks=? WHERE id=?", (json.dumps([block]), pid))
    before = snapshot(sid)
    other_before = snapshot(other)
    assert client.post(url(sid, pid) + "/confirm", json={}).status_code == 500
    assert snapshot(sid) == before
    assert snapshot(other) == other_before


def test_concurrent_confirm(scenario):
    """Concurrent requests execute once and return an idempotent second response."""
    client, sid, pid = scenario
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(url(sid, pid) + "/confirm", json={}), range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert sum(r.json().get("already_executed", False) for r in responses) == 1
    assert rows("sessions", sid)[0]["state_version"] == 2
    assert len([r for r in rows("execution_log", sid) if r["tool_name"] == "commit_schedule"]) == 1


def test_commit_preserves_persistent_meeting_uuids(scenario):
    """When proposed blocks omit explicit IDs, commit preserves existing meeting UUIDs."""
    client, sid, pid = scenario
    # Get original UUID of Team standup
    original_blocks = rows("calendar_blocks", sid)
    standup_orig = next(b for b in original_blocks if b["title"] == "Team standup")
    orig_uuid = standup_orig["id"]

    # Propose block without an 'id' field
    proposed = [
        {"title": "Team standup", "start_time": standup_orig["start_time"], "end_time": standup_orig["end_time"], "task_id": standup_orig["task_id"], "immutable": True}
    ]
    proposed.extend(b for b in original_blocks if b["id"] != orig_uuid)
    mutate("UPDATE plans SET proposed_blocks=? WHERE id=?", (json.dumps(proposed), pid))
    res = client.post(url(sid, pid) + "/confirm", json={})
    assert res.status_code == 200

    new_blocks = rows("calendar_blocks", sid)
    standup_new = next(b for b in new_blocks if b["title"] == "Team standup")
    assert standup_new["id"] == orig_uuid
