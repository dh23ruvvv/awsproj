"""Verify offline provider turns against real session, proposal, and commit tools."""

import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.providers import AgentContext, AgentTurnResult, DeterministicProvider
from server.providers.deterministic import PLAN_RESPONSE, REPLAN_RESPONSE, FALLBACK_RESPONSE


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    """Create a real seeded session and prohibit network connections."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "provider.db"))
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={
            "seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30",
        }).json()["session_id"]
        db = get_connection()
        yield client, AgentContext(sid, db)
        db.close()


def turn(context, message):
    """Run an asynchronous provider and check trace structure."""
    async def offline_turn():
        """Block sockets only after the Windows event loop has initialized."""
        with patch("socket.socket.connect", side_effect=AssertionError("Network access")):
            return await DeterministicProvider().run_agent_turn(message, context)

    result = asyncio.run(offline_turn())
    assert result.provider_used == "deterministic" and result.degraded is False
    for item in result.tool_trace:
        assert set(item) == {"tool", "args", "result_summary", "duration_ms"}
        assert item["duration_ms"] >= 0
        assert isinstance(item["args"], dict)
        json.loads(item["result_summary"])
    return result


def proposal(context, result):
    """Read persisted proposal blocks and diff."""
    row = context.db_conn.execute("SELECT * FROM plans WHERE id = ?", (result.plan_id,)).fetchone()
    assert row["status"] == "PROPOSED"
    return json.loads(row["proposed_blocks"]), json.loads(row["diff_summary"])


def confirm(client, context, result):
    """Commit a provider proposal through the public confirmation endpoint."""
    response = client.post(f"/api/v1/sessions/{context.session_id}/plans/{result.plan_id}/confirm",
                           json={"state_version": result.state_version})
    assert response.status_code == 200, response.text


def test_golden_turns(scenario):
    """Plan, commit, interrupt, commit, and restore using actual persisted state."""
    client, context = scenario
    first = turn(context, "Plan my day")
    assert first.response == PLAN_RESPONSE and first.has_proposal and first.state_version == 1
    assert [item["tool"] for item in first.tool_trace] == [
        "get_tasks", "get_calendar", "get_current_time", "get_memory", "propose_schedule"]
    blocks, _ = proposal(context, first)
    from datetime import datetime
    expected = {row["id"]: row["duration_minutes"] for row in context.db_conn.execute("SELECT * FROM tasks")}
    totals = {}
    for item in blocks:
        if item.get("task_id"):
            minutes = (datetime.fromisoformat(item["end_time"]) - datetime.fromisoformat(item["start_time"])).total_seconds() / 60
            totals[item["task_id"]] = totals.get(item["task_id"], 0) + minutes
    assert totals == expected
    assert context.db_conn.execute("SELECT count(*) FROM calendar_blocks").fetchone()[0] == 2
    confirm(client, context, first)
    context.db_conn.execute("UPDATE sessions SET demo_timestamp = ? WHERE id = ?",
                            ("2026-10-22T11:30:00+05:30", context.session_id))
    context.db_conn.commit()
    before = [dict(row) for row in context.db_conn.execute("SELECT * FROM calendar_blocks")]
    second = turn(context, "My manager scheduled a 1-on-1 at 2 PM for 30 minutes — replan around it.")
    assert second.response == REPLAN_RESPONSE and second.state_version == 2
    assert [item["tool"] for item in second.tool_trace] == ["get_schedule", "get_current_time", "get_tasks", "propose_replan"]
    blocks, diff = proposal(context, second)
    assert len(diff["moved"]) == 2 and not diff["shortened"] and not diff["dropped"]
    assert next(b for b in blocks if b["title"] == "Grocery shopping")["start_time"][11:16] == "15:30"
    assert next(b for b in blocks if b["title"] == "Gym session")["start_time"][11:16] == "14:30"
    for old in before:
        if old["end_time"] <= "2026-10-22T11:30:00+05:30":
            new = next(b for b in blocks if b.get("id") == old["id"])
            assert (new["start_time"], new["end_time"]) == (old["start_time"], old["end_time"])
    assert [dict(row) for row in context.db_conn.execute("SELECT * FROM calendar_blocks")] == before
    confirm(client, context, second)
    third = turn(AgentContext(context.session_id, context.db_conn), "What's left for today?")
    assert not third.has_proposal and third.plan_id is None and third.state_version == 3
    assert [item["tool"] for item in third.tool_trace] == ["get_schedule", "get_current_time", "get_memory"]
    assert "2:30 PM" in third.response and "3:30 PM" in third.response


@pytest.mark.parametrize("message", ["hello", "delete all data", "explain quantum physics"])
def test_fallback(scenario, message):
    """Unknown messages execute no tools and create no proposals."""
    _, context = scenario
    context.db_conn.execute("UPDATE sessions SET state_version = 7 WHERE id = ?", (context.session_id,))
    result = turn(context, message)
    assert result.response == FALLBACK_RESPONSE and result.state_version == 7
    assert result.tool_trace == [] and not result.has_proposal and result.plan_id is None
    assert context.db_conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_empty_status(scenario):
    """Completed days return a truthful empty summary without proposals."""
    _, context = scenario
    context.current_time = "2026-10-22T18:00:00+05:30"
    result = turn(context, "STATUS")
    assert result.response == "You have no remaining scheduled blocks today."
    assert not result.has_proposal


def test_independent_defaults():
    """Mutable dataclass defaults belong to individual turns and contexts."""
    first, second = AgentTurnResult("one"), AgentTurnResult("two")
    first.tool_trace.append({})
    assert second.tool_trace == []


def test_cancel_preserves_persisted_schedule(scenario):
    """A reviewed replan can be cancelled and reload keeps the committed plan."""
    client, context = scenario
    first = turn(context, "Plan my day")
    confirm(client, context, first)
    url = f"/api/v1/sessions/{context.session_id}"
    before = client.get(f"{url}/schedule").json()
    second = turn(context, "Replan around a meeting from 2:00 to 2:45 PM")
    assert second.has_proposal
    assert client.get(f"{url}/schedule").json() == before
    cancelled = client.post(f"{url}/plans/{second.plan_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled"] is True
    assert client.get(f"{url}/schedule").json() == before
    assert client.get(f"{url}/plans/{second.plan_id}").json()["status"] == "CANCELLED"
