"""Exercise fixed-event review, safe failure and provider rollback."""

import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from server.config import settings
from server.database import get_connection
from server.main import app
from server.providers.base import AgentContext
from server.providers.deterministic import DeterministicProvider
from server.providers.fallback import FallbackProvider
from server.tools.propose_tools import propose_schedule


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Create an isolated seeded workspace with no network provider."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "events.db"))
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")
    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
        yield client, f"/api/v1/sessions/{sid}", sid


def test_fixed_client_meeting_review_cancel_confirm_and_replan(workspace):
    """A user reviews the client event and it survives a later urgent meeting."""
    client, url, _ = workspace
    initial = client.get(url + "/schedule").json()
    event = {"title": "Client meeting", "start_time": "2026-10-22T15:30:00+05:30", "end_time": "2026-10-22T16:00:00+05:30", "state_version": 1}
    response = client.post(url + "/commitments", json=event)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert len(proposal["diff"]["added"]) == 1
    assert client.get(url + "/schedule").json() == initial
    client.post(url + f"/plans/{proposal['plan_id']}/cancel")
    assert client.get(url + "/schedule").json() == initial
    proposal = client.post(url + "/commitments", json=event).json()
    confirmed = client.post(url + f"/plans/{proposal['plan_id']}/confirm", json={"state_version": 1})
    assert confirmed.status_code == 200
    saved = client.get(url + "/schedule").json()
    meeting = next(b for b in saved["blocks"] if b["title"] == "Client meeting")
    assert meeting["immutable"]
    replanned = client.post(url + "/agent/message", json={"message": "An urgent meeting from 2:00 to 2:45 PM. Rework my afternoon but don't move the client meeting.", "state_version": 2}).json()
    assert replanned["has_proposal"]
    details = client.get(url + f"/plans/{replanned['plan_id']}").json()
    assert next(b for b in details["proposed_blocks"] if b.get("id") == meeting["id"]) == meeting
    assert client.get(url + "/schedule").json() == saved


@pytest.mark.parametrize("changes,code", [
    ({"state_version": 99}, 409),
    ({"title": "   "}, 422),
    ({"start_time": "2026-10-22T10:00:00+05:30", "end_time": "2026-10-22T10:15:00+05:30"}, 422),
    ({"end_time": "2026-10-22T14:00:00+05:30"}, 422),
    ({"start_time": "2026-10-22T15:00:00"}, 422),
    ({"end_time": "invalid"}, 422),
])
def test_invalid_fixed_event_never_changes_saved_state(workspace, changes, code):
    """Reject stale, conflicting, reversed or malformed event requests."""
    client, url, _ = workspace
    before = client.get(url + "/schedule").json()
    event = {"title": "Client meeting", "start_time": "2026-10-22T15:30:00+05:30", "end_time": "2026-10-22T16:00:00+05:30", "state_version": 1, **changes}
    assert client.post(url + "/commitments", json=event).status_code == code
    assert client.get(url + "/schedule").json() == before


def test_failed_primary_proposal_is_rolled_back_before_fallback(workspace):
    """A provider timeout after proposing does not leave an orphan draft or cancel a reviewed draft."""
    _, _, sid = workspace
    db = get_connection()
    try:
        original = propose_schedule(sid, {"blocks": [], "explanation": "Existing review"}, db)["plan_id"]
        async def failing_primary(message, context):
            """Simulate a timeout after tools have already stored a draft."""
            propose_schedule(sid, {"blocks": [], "explanation": "Orphan"}, db)
            raise TimeoutError("Simulated provider interruption")
        primary = AsyncMock()
        primary.run_agent_turn.side_effect = failing_primary
        result = asyncio.run(FallbackProvider(primary, DeterministicProvider()).run_agent_turn("hello", AgentContext(sid, db)))
        assert result.degraded and not result.has_proposal
        assert db.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 1
        assert db.execute("SELECT status FROM plans WHERE id=?", (original,)).fetchone()[0] == "PROPOSED"
    finally:
        db.close()
