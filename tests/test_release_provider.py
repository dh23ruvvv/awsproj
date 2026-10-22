"""The offline path interprets supported requests without inventing constraints."""

import asyncio
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from server.config import settings
from server.database import get_connection
from server.main import app
from server.providers import AgentContext, DeterministicProvider
from server.providers.deterministic import _interruption


@pytest.mark.parametrize("utterance,start,end", [
    ("rework from 2:00 to 2:45 pm", "14:00", "14:45"),
    ("replan from 11:30 am to 1:00 pm", "11:30", "13:00"),
    ("replan from 14:00 to 14:45", "14:00", "14:45"),
    ("manager 1-on-1 at 2 pm for 30 minutes", "14:00", "14:30"),
])
def test_explicit_interval(utterance, start, end):
    block = _interruption(utterance, datetime.fromisoformat("2026-10-22T09:00:00+05:30"))
    assert block["start_time"][11:16] == start
    assert block["end_time"][11:16] == end
    assert block["immutable"] is True
    assert block["start_time"].endswith("+05:30")


@pytest.mark.parametrize("utterance", [
    "replan my afternoon", "replan from 2:00 to 2:99 pm",
    "replan from 3 pm to 2 pm", "replan tomorrow from 2 pm to 3 pm",
    "replan from 2 pm to 3 pm and from 4 pm to 5 pm",
    "replan at 2 pm for 0 minutes", "replan from 2 pm to 3 pm pst",
])
def test_ambiguous_or_invalid_interval(utterance):
    with pytest.raises(ValueError):
        _interruption(utterance, datetime.fromisoformat("2026-10-22T09:00:00+05:30"))


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "release_provider.db"))
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={
            "seed": True, "demo_timestamp": "2026-10-22T09:00:00+05:30",
        }).json()["session_id"]
        db = get_connection()
        try:
            yield AgentContext(sid, db)
        finally:
            db.close()


def turn(context, message):
    return asyncio.run(DeterministicProvider().run_agent_turn(message, context))


def test_real_rework_proposal_preserves_calendar(context):
    before = [dict(row) for row in context.db_conn.execute("SELECT * FROM calendar_blocks")]
    result = turn(context, "An urgent meeting just came up from 2:00 to 2:45 PM. Rework my afternoon but don't move the client meeting.")
    assert result.has_proposal
    row = context.db_conn.execute("SELECT proposed_blocks FROM plans WHERE id = ?", (result.plan_id,)).fetchone()
    blocks = json.loads(row[0])
    interruption = next(b for b in blocks if b["title"] == "Unexpected meeting")
    assert interruption["start_time"][11:16] == "14:00"
    assert interruption["end_time"][11:16] == "14:45"
    assert [dict(row) for row in context.db_conn.execute("SELECT * FROM calendar_blocks")] == before
    for original in before:
        preserved = next(b for b in blocks if b.get("id") == original["id"])
        assert preserved["start_time"] == original["start_time"]
        assert preserved["end_time"] == original["end_time"]


@pytest.mark.parametrize("message", ["Rework my afternoon", "Plan my day and add a new task for 120 minutes"])
def test_unsupported_request_does_not_create_proposal(context, message):
    result = turn(context, message)
    assert not result.has_proposal
    assert context.db_conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0
    assert "Deterministic" in result.response or "explicit times" in result.response


def test_protected_conflict_is_recoverable(context):
    result = turn(context, "Replan from 10:00 to 10:15 AM")
    assert not result.has_proposal
    assert "unchanged" in result.response
    assert context.db_conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_plan_narration_does_not_invent_demo_outcomes(context):
    result = turn(context, "Plan my day")
    assert result.has_proposal
    assert "confirm" in result.response
    assert "5 PM" not in result.response
    assert "three blocks" not in result.response

