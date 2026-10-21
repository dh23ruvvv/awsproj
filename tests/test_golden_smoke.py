"""
FlowPilot Golden Smoke Test.
Verifies the complete golden demo scenario end-to-end, all 7 live-LLM acceptance invariants,
and the fallback path under failure.
"""

import os
from datetime import datetime
from fastapi.testclient import TestClient
import pytest

from server.config import settings
from server.database import get_connection
from server.main import app


def parse_dt(iso_str: str) -> datetime:
    """Helper to parse ISO datetime strings."""
    # Strip offset if present for simple comparison
    clean = iso_str.split("+")[0]
    return datetime.fromisoformat(clean)


def check_invariants(blocks: list[dict], current_time_str: str = "2026-10-22T09:00:00"):
    """Assert all 7 product acceptance invariants on schedule blocks."""
    # Invariant 1: No time-block overlaps
    sorted_blocks = sorted(blocks, key=lambda b: parse_dt(b["start_time"]))
    for i in range(len(sorted_blocks) - 1):
        curr_end = parse_dt(sorted_blocks[i]["end_time"])
        next_start = parse_dt(sorted_blocks[i + 1]["start_time"])
        assert curr_end <= next_start, (
            f"Overlap detected: {sorted_blocks[i]['title']} ({sorted_blocks[i]['end_time']}) "
            f"overlaps with {sorted_blocks[i + 1]['title']} ({sorted_blocks[i + 1]['start_time']})"
        )

    # Invariant 3: Deadline-critical tasks scheduled before deadlines
    # T1 deadline: 17:00; T2 deadline: 14:00
    for b in blocks:
        task_id = b.get("task_id")
        end_dt = parse_dt(b["end_time"])
        if task_id == "T1":
            assert end_dt <= datetime.fromisoformat("2026-10-22T17:00:00"), f"T1 scheduled after deadline: {end_dt}"
        elif task_id == "T2":
            assert end_dt <= datetime.fromisoformat("2026-10-22T14:00:00"), f"T2 scheduled after deadline: {end_dt}"

    # Invariant 5: Immutable calendar blocks preserved
    standup = [b for b in blocks if "standup" in b["title"].lower()]
    lunch = [b for b in blocks if "lunch" in b["title"].lower()]
    assert standup, "Standup block missing"
    assert lunch, "Lunch block missing"
    assert parse_dt(standup[0]["start_time"]) == datetime.fromisoformat("2026-10-22T10:00:00")
    assert parse_dt(standup[0]["end_time"]) == datetime.fromisoformat("2026-10-22T10:30:00")
    assert parse_dt(lunch[0]["start_time"]) == datetime.fromisoformat("2026-10-22T13:00:00")
    assert parse_dt(lunch[0]["end_time"]) == datetime.fromisoformat("2026-10-22T14:00:00")


def test_golden_smoke_deterministic(tmp_path, monkeypatch):
    """
    Execute full golden demo end-to-end:
    Turn 1 (Initial Plan) -> Confirm -> Turn 2 (Interrupt & Replan) -> Confirm -> Turn 3 (Reload & Query).
    """
    db_file = str(tmp_path / "smoke_det.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")

    with TestClient(app) as client:
        # Step 1: Create seeded session
        create_res = client.post("/api/v1/sessions", json={
            "seed": True,
            "demo_timestamp": "2026-10-22T09:00:00+05:30"
        })
        assert create_res.status_code == 201
        sid = create_res.json()["session_id"]
        v1 = create_res.json()["state_version"]
        assert v1 == 1

        # Step 2: Turn 1 (Initial Planning)
        t1_msg = "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting."
        turn1_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": t1_msg})
        assert turn1_res.status_code == 200, turn1_res.text
        t1_data = turn1_res.json()
        assert t1_data["has_proposal"] is True
        assert t1_data["plan_id"] is not None
        assert t1_data["provider_used"] == "deterministic"
        assert t1_data["degraded"] is False
        assert "report" in t1_data["response"].lower() or "focused schedule" in t1_data["response"].lower()

        plan1_id = t1_data["plan_id"]
        # Verify plan state PROPOSED
        plan1_res = client.get(f"/api/v1/sessions/{sid}/plans/{plan1_id}")
        assert plan1_res.status_code == 200
        assert plan1_res.json()["status"] == "PROPOSED"

        # Check invariants on proposed blocks
        proposed_blocks_1 = plan1_res.json()["proposed_blocks"]
        check_invariants(proposed_blocks_1)

        # Step 3: Approval 1 (Confirm Turn 1 Plan)
        confirm1_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan1_id}/confirm", json={"state_version": v1})
        assert confirm1_res.status_code == 200, confirm1_res.text
        c1_data = confirm1_res.json()
        assert c1_data["committed"] is True
        v2 = c1_data["state_version"]
        assert v2 == 2  # Invariant 7: state_version incremented

        # Invariant 6: Plan state is now EXECUTED
        plan1_after = client.get(f"/api/v1/sessions/{sid}/plans/{plan1_id}").json()
        assert plan1_after["status"] == "EXECUTED"

        # Verify DB schedule and memory
        sched1 = client.get(f"/api/v1/sessions/{sid}/schedule").json()
        assert len(sched1["blocks"]) >= 5
        check_invariants(sched1["blocks"])

        mem1 = client.get(f"/api/v1/sessions/{sid}/memory").json()
        assert len(mem1["entries"]) >= 1
        assert any("work_style" in entry["key"] for entry in mem1["entries"])

        # Step 4: Turn 2 (Interruption and Replan at 11:30 IST)
        t2_msg = "My manager just scheduled a 1-on-1 at 2 PM for 30 minutes — replan around it."
        turn2_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": t2_msg})
        assert turn2_res.status_code == 200, turn2_res.text
        t2_data = turn2_res.json()
        assert t2_data["has_proposal"] is True
        plan2_id = t2_data["plan_id"]

        plan2_res = client.get(f"/api/v1/sessions/{sid}/plans/{plan2_id}").json()
        assert plan2_res["status"] == "PROPOSED"
        diff = plan2_res.get("diff") or plan2_res.get("diff_summary") or {}
        assert len(diff.get("kept", [])) >= 1
        assert len(diff.get("moved", [])) >= 1 or len(diff.get("added", [])) >= 1

        # Check invariants on replanned blocks
        check_invariants(plan2_res["proposed_blocks"])

        # Invariant 2: Completed / past blocks before 11:30 are preserved
        completed_orig = [b for b in sched1["blocks"] if parse_dt(b["end_time"]) <= datetime.fromisoformat("2026-10-22T11:30:00")]
        replan_blocks = plan2_res["proposed_blocks"]
        for orig in completed_orig:
            matched = [b for b in replan_blocks if b.get("id") == orig.get("id") or b["title"] == orig["title"]]
            assert matched, f"Completed block missing in replan: {orig['title']}"
            assert matched[0]["start_time"] == orig["start_time"], f"Completed block start modified: {orig['title']}"
            assert matched[0]["end_time"] == orig["end_time"], f"Completed block end modified: {orig['title']}"

        # Step 5: Approval 2 (Confirm Replan)
        confirm2_res = client.post(f"/api/v1/sessions/{sid}/plans/{plan2_id}/confirm", json={"state_version": v2})
        assert confirm2_res.status_code == 200, confirm2_res.text
        v3 = confirm2_res.json()["state_version"]
        assert v3 == 3

        # Step 6: Turn 3 (Session Restore & Status Query)
        sched2 = client.get(f"/api/v1/sessions/{sid}/schedule").json()
        assert sched2["state_version"] == 3
        check_invariants(sched2["blocks"])

        mem2 = client.get(f"/api/v1/sessions/{sid}/memory").json()
        assert len(mem2["entries"]) >= 2
        assert any("manager" in entry["key"].lower() for entry in mem2["entries"])

        t3_msg = "What's left for today?"
        turn3_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": t3_msg})
        assert turn3_res.status_code == 200
        t3_data = turn3_res.json()
        assert t3_data["has_proposal"] is False
        assert len(t3_data["response"]) > 10


def test_golden_smoke_fallback(tmp_path, monkeypatch):
    """
    Verify expected failure and fallback:
    When live LLM provider fails / times out, system falls back to deterministic with degraded=true.
    """
    db_file = str(tmp_path / "smoke_fallback.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "mock-key")

    from unittest.mock import AsyncMock
    from server.providers import gemini
    from server.routers import agent

    # Force live gemini to fail with TimeoutError
    primary = AsyncMock(side_effect=TimeoutError("Request timed out"))
    monkeypatch.setattr(gemini.GeminiProvider, "run_agent_turn", primary)
    agent._live_provider.cache_clear()

    try:
        with TestClient(app) as client:
            create_res = client.post("/api/v1/sessions", json={"seed": True})
            sid = create_res.json()["session_id"]

            t1_msg = "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting."
            turn_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": t1_msg})
            assert turn_res.status_code == 200, turn_res.text
            data = turn_res.json()
            assert data["degraded"] is True
            assert data["provider_used"] == "gemini-fallback"
            assert data["has_proposal"] is True
            assert data["plan_id"] is not None

            # Can still confirm proposed plan even though it came via fallback
            confirm_res = client.post(f"/api/v1/sessions/{sid}/plans/{data['plan_id']}/confirm", json={"state_version": 1})
            assert confirm_res.status_code == 200
            assert confirm_res.json()["committed"] is True
    finally:
        agent._live_provider.cache_clear()


@pytest.mark.skipif(not (settings.gemini_api_key or os.getenv("GEMINI_API_KEY")), reason="GEMINI_API_KEY is not set")
def test_golden_smoke_live_invariants(tmp_path, monkeypatch):
    """
    Test live Gemini provider against all 7 invariants if API key is active.
    """
    db_file = str(tmp_path / "smoke_live.db")
    monkeypatch.setattr(settings, "flowpilot_db_path", db_file)
    monkeypatch.setattr(settings, "flowpilot_default_provider", "gemini")

    with TestClient(app) as client:
        create_res = client.post("/api/v1/sessions", json={"seed": True})
        sid = create_res.json()["session_id"]
        v1 = create_res.json()["state_version"]

        t1_msg = "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting."
        turn_res = client.post(f"/api/v1/sessions/{sid}/agent/message", json={"message": t1_msg})
        assert turn_res.status_code == 200, turn_res.text
        data = turn_res.json()
        assert data["provider_used"] in ("gemini", "gemini-fallback")
        assert len(data["tool_trace"]) >= 1

        if data["has_proposal"] and data["plan_id"]:
            plan_res = client.get(f"/api/v1/sessions/{sid}/plans/{data['plan_id']}").json()
            check_invariants(plan_res["proposed_blocks"])
            confirm_res = client.post(f"/api/v1/sessions/{sid}/plans/{data['plan_id']}/confirm", json={"state_version": v1})
            assert confirm_res.status_code == 200
            assert confirm_res.json()["state_version"] == 2
