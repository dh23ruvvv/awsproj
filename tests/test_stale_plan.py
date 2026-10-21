"""
Stale Plan tests:
Verifies that when session state_version has moved ahead, attempting to confirm an older
proposal is rejected with HTTP 409 STALE_PLAN and transitions plan status to STALE.
"""

from fastapi.testclient import TestClient
from server.config import settings
from server.database import get_connection
from server.main import app


def test_stale_plan_rejected_with_409(tmp_path, monkeypatch):
    """A proposal created against state_version=1 cannot be confirmed if the session advanced to state_version=2."""
    db_file = str(tmp_path / "stale_plan.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")

    with TestClient(app) as client:
        # Create seeded session (version = 1)
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]

        # Propose plan 1 at state_version = 1
        msg_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "Plan my day"})
        assert msg_res.status_code == 200
        plan1_id = msg_res.json()["plan_id"]
        assert plan1_id is not None

        # Verify plan 1 is PROPOSED with state_version_at_proposal = 1
        plan1 = client.get(f"/api/v1/sessions/{sid}/plans/{plan1_id}").json()
        assert plan1["status"] == "PROPOSED"
        assert plan1["state_version_at_proposal"] == 1

        # Advance session state_version by performing an out-of-band mutation (e.g., another update or direct version bump)
        db = get_connection()
        db.execute("UPDATE sessions SET state_version = 2 WHERE id = ?", (sid,))
        db.commit()

        # Now attempt to confirm plan 1 -> Must return 409 STALE_PLAN
        confirm_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan1_id}/confirm", json={"state_version": 1})
        assert confirm_res.status_code == 409
        error_envelope = confirm_res.json()
        assert error_envelope["error"]["code"] == "STALE_PLAN"
        assert "expected" in error_envelope["error"]["details"]
        assert "current" in error_envelope["error"]["details"]

        # Verify plan status was updated to STALE
        plan_after = db.execute("SELECT status FROM plans WHERE id = ?", (plan1_id,)).fetchone()
        assert plan_after["status"] == "STALE"

        # Verify session state_version remains 2 and no domain blocks were added from plan 1
        curr_ver = db.execute("SELECT state_version FROM sessions WHERE id = ?", (sid,)).fetchone()[0]
        assert curr_ver == 2
        blocks_from_plan = db.execute("SELECT count(*) FROM calendar_blocks WHERE plan_id = ?", (plan1_id,)).fetchone()[0]
        assert blocks_from_plan == 0
        db.close()


def test_explicit_mismatched_state_version_rejected(tmp_path, monkeypatch):
    """Passing a state_version different from the session state returns 409."""
    db_file = str(tmp_path / "stale_param.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)

    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
        msg_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "Plan my day"})
        plan_id = msg_res.json()["plan_id"]

        # Proposal is at version 1, but client explicitly supplies state_version = 99
        bad_confirm = client.post(f"/api/v1/sessions/{sid}/plans/{plan_id}/confirm", json={"state_version": 99})
        assert bad_confirm.status_code == 409
        assert bad_confirm.json()["error"]["code"] == "STALE_PLAN"
