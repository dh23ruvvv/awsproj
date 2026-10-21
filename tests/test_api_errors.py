"""Regression tests for BUG-001 and BUG-002.

Ensures that:
1. Global exception handlers return structured JSON ErrorEnvelope on 500 and 422 errors.
2. validate_schedule correctly matches immutable blocks by title/task_id even when id is omitted.
"""

from fastapi.testclient import TestClient
import pytest

from server.engine.validator import validate_schedule
from server.main import app


def test_validation_error_envelope():
    """Invalid payload formats return a structured JSON ErrorEnvelope."""
    with TestClient(app) as client:
        res = client.post("/api/v1/sessions/any-id/agent/message", json={"message": ""})
        assert res.status_code == 422
        assert res.headers["content-type"].startswith("application/json")
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "Invalid request payload" in data["error"]["message"]


def test_404_error_envelope():
    """Missing routes or entities return structured JSON ErrorEnvelope."""
    with TestClient(app) as client:
        res = client.get("/api/v1/nonexistent-route")
        assert res.status_code == 404
        assert res.headers["content-type"].startswith("application/json")
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_404"


def test_validator_immutable_blocks_matching_by_title():
    """BUG-002 regression: LLM proposal blocks without DB 'id' matching protected blocks pass validation."""
    existing = [
        {
            "id": "existing-uuid-1",
            "title": "Team standup",
            "start_time": "2026-10-22T10:00:00+05:30",
            "end_time": "2026-10-22T10:30:00+05:30",
            "immutable": True,
            "task_id": "task-uuid-1",
        },
        {
            "id": "existing-uuid-2",
            "title": "Lunch",
            "start_time": "2026-10-22T13:00:00+05:30",
            "end_time": "2026-10-22T14:00:00+05:30",
            "immutable": True,
            "task_id": None,
        },
    ]

    # Proposed blocks from LLM without 'id' field
    proposed = [
        {
            "title": "Planning",
            "start_time": "2026-10-22T09:00:00+05:30",
            "end_time": "2026-10-22T09:05:00+05:30",
        },
        {
            "title": "Team standup",
            "start_time": "2026-10-22T10:00:00+05:30",
            "end_time": "2026-10-22T10:30:00+05:30",
            "immutable": True,
        },
        {
            "title": "Lunch",
            "start_time": "2026-10-22T13:00:00+05:30",
            "end_time": "2026-10-22T14:00:00+05:30",
            "immutable": True,
        },
    ]

    errors = validate_schedule(proposed, existing, "2026-10-22T09:00:00+05:30")
    assert errors == [], f"Expected no validation errors, got: {errors}"


def test_validator_immutable_blocks_rejects_moved_protected_block():
    """Protected blocks moved to a different time must still be rejected."""
    existing = [
        {
            "id": "existing-uuid-1",
            "title": "Team standup",
            "start_time": "2026-10-22T10:00:00+05:30",
            "end_time": "2026-10-22T10:30:00+05:30",
            "immutable": True,
            "task_id": "task-uuid-1",
        },
    ]

    # Proposed block moved Team standup to 11:00
    proposed = [
        {
            "title": "Team standup",
            "start_time": "2026-10-22T11:00:00+05:30",
            "end_time": "2026-10-22T11:30:00+05:30",
            "immutable": True,
        },
    ]

    errors = validate_schedule(proposed, existing, "2026-10-22T09:00:00+05:30")
    assert any("Protected completed/immutable block modified or removed" in err for err in errors)
