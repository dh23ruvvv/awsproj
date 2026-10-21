"""Verify the pinned timetables and pure engine invariants."""

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
    """Exact timetable timestamps override the report's duration estimate."""
    original = deepcopy(seed)
    blocks = compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
    assert times(blocks) == [("09:00", "09:05"), ("09:05", "10:00"), ("10:00", "10:30"), ("10:30", "11:15"), ("11:15", "12:15"), ("12:15", "13:00"), ("13:00", "14:00"), ("14:00", "14:45"), ("15:00", "16:00"), ("16:00", "17:00")]
    assert [block.get("task_id") for block in blocks] == [None, "T1", "T4", "T2", "T1", "T5", None, "T1", "T3", None]
    assert validate_schedule(blocks, seed["calendar_blocks"], seed["demo_timestamp"]) == []
    assert seed == original


def test_turn_two(seed):
    """Replanning preserves completed work and spends buffer on the new meeting."""
    old = compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
    original = deepcopy(old)
    meeting = {"title": "Manager 1-on-1", "start_time": "2026-10-22T14:00:00+05:30", "end_time": "2026-10-22T14:30:00+05:30", "immutable": True}
    new = compute_replan(old, meeting, "2026-10-22T11:30:00+05:30")
    assert times(new) == [("09:05", "10:00"), ("10:00", "10:30"), ("10:30", "11:15"), ("11:15", "12:15"), ("12:15", "13:00"), ("13:00", "14:00"), ("14:00", "14:30"), ("14:30", "15:15"), ("15:15", "16:15"), ("16:15", "17:00")]
    assert all(block["status"] == "completed" for block in new[:3])
    diff = compute_diff(old, new)
    assert len(diff["kept"]) == 6
    assert len(diff["moved"]) == 3
    assert diff["shortened"][0]["new_duration_min"] == 45
    assert diff["dropped"][0]["title"] == "Planning"
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
    assert not diff["added"] and not diff["dropped"]
    assert compute_diff([], []) == {key: [] for key in ("kept", "moved", "shortened", "dropped", "added")}


def test_impossible_deadline(seed):
    """Never silently emit a reservation past a task deadline."""
    seed["tasks"][0]["deadline"] = "2026-10-22T09:30:00+05:30"
    with pytest.raises(ValueError, match="deadline"):
        compute_day_schedule(seed["tasks"], seed["calendar_blocks"], seed["demo_timestamp"])
