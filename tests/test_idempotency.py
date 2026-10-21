"""
Idempotency tests:
Verifies that duplicate confirm requests return already_executed with no duplicate blocks or side-effects.
"""

from fastapi.testclient import TestClient
from server.config import settings
from server.database import get_connection
from server.main import app


def test_confirm_plan_idempotency(tmp_path, monkeypatch):
    """Confirming an already executed plan returns already_executed=True without duplicating database state."""
    db_file = str(tmp_path / "idempotency.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")

    with TestClient(app) as client:
        # Create seeded session
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]

        # Propose plan
        msg_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "Plan my day"})
        assert msg_res.status_code == 200
        plan_id = msg_res.json()["plan_id"]
        assert plan_id is not None

        # First confirm
        c1_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan_id}/confirm", json={"state_version": 1})
        assert c1_res.status_code == 200
        c1 = c1_res.json()
        assert c1["committed"] is True
        assert c1["already_executed"] is False
        assert c1["state_version"] == 2

        # Count blocks in DB
        db = get_connection()
        count_after_first = db.execute("SELECT count(*) FROM calendar_blocks WHERE session_id = ?", (sid,)).fetchone()[0]
        assert count_after_first > 2

        # Second confirm with the same plan
        c2_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan_id}/confirm", json={"state_version": 2})
        assert c2_res.status_code == 200
        c2 = c2_res.json()
        assert c2["committed"] is True
        assert c2["already_executed"] is True
        assert c2["state_version"] == 2  # State version not incremented again

        # Verify DB blocks count has not increased
        count_after_second = db.execute("SELECT count(*) FROM calendar_blocks WHERE session_id = ?", (sid,)).fetchone()[0]
        assert count_after_second == count_after_first

        # Verify plan status remains EXECUTED
        plan_row = db.execute("SELECT status FROM plans WHERE id = ?", (plan_id,)).fetchone()
        assert plan_row["status"] == "EXECUTED"
        db.close()


def test_cannot_confirm_cancelled_plan(tmp_path, monkeypatch):
    """A cancelled plan cannot be confirmed."""
    db_file = str(tmp_path / "cancel_confirm.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)

    with TestClient(app) as client:
        sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
        msg_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": "Plan my day"})
        plan_id = msg_res.json()["plan_id"]

        # Cancel the plan
        cancel_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["cancelled"] is True

        # Attempt to confirm cancelled plan -> should fail
        confirm_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan_id}/confirm", json={"state_version": 1})
        assert confirm_res.status_code in (400, 409, 422)
        error_envelope = confirm_res.json()
        assert "error" in error_envelope
