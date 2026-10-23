"""Verify truthful task durations and pure engine invariants."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from server.engine import compute_day_schedule, compute_replan, compute_diff, validate_schedule


@pytest.fixture
def seed():
    """Load the authoritative demo inputs."""
    return json.loads((Path(__file__).parents[1] / "server" / "seed.json").read_text(encoding="utf-8"))


def times(blocks):
    """Return readable local interval pairs."""
    return [(block["start_time"][11:16], block["end_time"][11:16]) for block in blocks]


def test_turn_one(seed):
    """Schedule actual task estimates in free intervals, without fake reservations."""
    original = deepcopy(seed)
    blocks = compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
    assert times(blocks) == [("09:00", "09:45"), ("10:00", "10:30"),
                             ("10:30", "12:30"), ("13:00", "14:00"),
                             ("14:00", "15:00"), ("15:00", "16:00")]
    assert [block.get("task_id") for block in blocks] == ["T2", "T4", "T1", None, "T5", "T3"]
    assert validate_schedule(blocks, seed["calendar_blocks"], seed["demo_timestamp"]) == []
    assert seed == original


def test_turn_two(seed):
    """Replanning preserves all work, without manufacturing completed statuses."""
    old = compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
    original = deepcopy(old)
    meeting = {"title": "Manager 1-on-1", "start_time": "2026-10-22T14:00:00+05:30", "end_time": "2026-10-22T14:30:00+05:30", "immutable": True}
    new = compute_replan(old, meeting, "2026-10-22T11:30:00+05:30")
    assert times(new) == [("09:00", "09:45"), ("10:00", "10:30"),
                         ("10:30", "12:30"), ("13:00", "14:00"),
                         ("14:00", "14:30"), ("14:30", "15:30"), ("15:30", "16:30")]
    diff = compute_diff(old, new)
    assert len(diff["kept"]) == 4
    assert len(diff["moved"]) == 2
    assert not diff["shortened"] and not diff["dropped"]
    assert diff["added"] == [{key: meeting[key] for key in ("title", "start_time", "end_time")}]
    assert old == original


@pytest.mark.parametrize("change", ["overlap", "invalid", "reverse", "day", "timezone"])
def test_invalid_intervals(seed, change):
    """Reject malformed, overlapping, reversed, or cross-day intervals."""
    blocks = deepcopy(seed["calendar_blocks"])
    if change == "overlap":
        blocks[1]["start_time"] = blocks[0]["start_time"]
    elif change == "invalid":
        blocks[0]["start_time"] = "2026-10-22"
    elif change == "reverse":
        blocks[0]["end_time"] = blocks[0]["start_time"]
    elif change == "day":
        blocks[0]["start_time"] = "2026-10-21T10:00:00+05:30"
    else:
        blocks[0]["start_time"] = "2026-10-22T10:00:00"
    assert validate_schedule(blocks, current_time=seed["demo_timestamp"])


@pytest.mark.parametrize("mutation", ["move", "shorten", "remove"])
def test_completed_preservation(seed, mutation):
    """A completed block cannot be changed or omitted."""
    old = deepcopy(seed["calendar_blocks"][:1])
    old[0]["status"] = "COMPLETED"
    old[0]["immutable"] = False
    new = deepcopy(old)
    if mutation == "move":
        new[0]["start_time"] = "2026-10-22T10:05:00+05:30"
    elif mutation == "shorten":
        new[0]["end_time"] = "2026-10-22T10:15:00+05:30"
    else:
        new.clear()
    assert validate_schedule(new, old)
    assert validate_schedule(old, old) == []


def test_diff_persistent_identity(seed):
    """Renaming a persistent block preserves identity; shortening can also move it."""
    old = deepcopy(seed["calendar_blocks"][:1])
    old[0]["id"] = "block-1"
    new = deepcopy(old)
    new[0].update(title="Renamed", start_time="2026-10-22T10:15:00+05:30")
    diff = compute_diff(old, new)
    assert diff["moved"][0]["block_id"] == "block-1"
    assert diff["shortened"][0]["new_duration_min"] == 15
    assert compute_diff([], []) == {key: [] for key in ("kept", "moved", "shortened", "lengthened", "dropped", "added")}


def test_diff_detects_lengthened_block(seed):
    """Extending a block duration populates the lengthened diff category."""
    old = deepcopy(seed["calendar_blocks"][:1])
    old[0]["id"] = "block-1"
    old[0]["start_time"] = "2026-10-22T10:00:00+05:30"
    old[0]["end_time"] = "2026-10-22T10:30:00+05:30"
    new = deepcopy(old)
    new[0]["end_time"] = "2026-10-22T11:00:00+05:30"
    diff = compute_diff(old, new)
    assert len(diff["lengthened"]) == 1
    assert diff["lengthened"][0]["block_id"] == "block-1"
    assert diff["lengthened"][0]["old_duration_min"] == 30
    assert diff["lengthened"][0]["new_duration_min"] == 60
    assert not diff["kept"] and not diff["shortened"]


def test_impossible_deadline(seed):
    """Never silently emit a reservation past a task deadline."""
    seed["tasks"][0]["deadline"] = "2026-10-22T09:30:00+05:30"
    with pytest.raises(ValueError, match="deadline"):
        compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])


def block(title, start, end, **extra):
    return {"title": title, "start_time": f"2026-10-22T{start}:00+05:30",
            "end_time": f"2026-10-22T{end}:00+05:30", **extra}


def test_replan_jumps_over_immutable_meeting():
    old = [block("Work", "14:00", "15:00", id="work-id", task_id="task-id"),
           block("Client Sync", "15:30", "16:00", immutable=True)]
    new = compute_replan(old, block("Emergency", "14:00", "14:45"), "2026-10-22T11:30:00+05:30")
    work = next(b for b in new if b["title"] == "Work")
    assert work["start_time"][11:16] == "16:00"
    assert work["end_time"][11:16] == "17:00"
    assert work["id"] == "work-id" and work["task_id"] == "task-id"
    assert old[1] in new
    assert validate_schedule(new, old, "2026-10-22T11:30:00+05:30") == []


@pytest.mark.parametrize("minutes", [30, 61, 120, 180])
@pytest.mark.parametrize("category", ["personal", "work"])
def test_true_duration(seed, minutes, category):
    task = dict(seed["tasks"][0], duration_minutes=minutes, category=category)
    blocks = compute_day_schedule([task], [], seed["demo_timestamp"])
    from datetime import datetime
    assert len(blocks) == 1
    duration = datetime.fromisoformat(blocks[0]["end_time"]) - datetime.fromisoformat(blocks[0]["start_time"])
    assert duration.total_seconds() == minutes * 60


@pytest.mark.parametrize("extra", [{"immutable": True}, {"status": "completed"}, {}])
def test_interruption_cannot_move_protected_or_in_progress(extra):
    old = [block("Work", "10:00", "12:00", **extra)]
    with pytest.raises(ValueError, match="protected or in-progress"):
        compute_replan(old, block("Emergency", "11:00", "11:30"), "2026-10-22T10:30:00+05:30")


def test_completed_future_block_stays_fixed():
    old = [block("Done", "14:00", "15:00", status="completed")]
    with pytest.raises(ValueError, match="protected"):
        compute_replan(old, block("Emergency", "14:30", "15:00"), "2026-10-22T09:00:00+05:30")


def test_replan_impossible_day_fails_without_mutation():
    old = [block("Work", "15:00", "17:00", id="stable", deadline="2026-10-22T17:00:00+05:30")]
    original = deepcopy(old)
    with pytest.raises(ValueError, match="full 120 minutes"):
        compute_replan(old, block("Emergency", "15:00", "16:00"), "2026-10-22T09:00:00+05:30")
    assert old == original


def test_plan_again_preserves_existing_identity(seed):
    planned = compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
    for index, item in enumerate(planned):
        item["id"] = f"persistent-{index}"
    assert compute_day_schedule(seed["tasks"], planned, seed["demo_timestamp"]) == planned


def test_replan_uses_gap_before_later_protected_event():
    old = [block("Work", "14:00", "14:30"),
           block("Fixed", "16:00", "17:00", immutable=True)]
    new = compute_replan(old, block("Emergency", "14:00", "14:45"), "2026-10-22T09:00:00+05:30")
    assert next(b for b in new if b["title"] == "Work")["start_time"][11:16] == "14:45"


def test_timezone_required(seed):
    with pytest.raises(ValueError, match="timezone"):
        compute_day_schedule([], [], "2026-10-22T09:00:00")
