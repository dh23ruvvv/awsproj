"""Exercise persisted proposals, protection rules, and domain-state isolation."""

import json
from copy import deepcopy
import sqlite3

import pytest

from server.database import SCHEMA, get_connection, seed_session
from server.tools.registry import default_registry


@pytest.fixture
def db():
    """Create isolated sessions using the authoritative seed date."""
    connection = get_connection(":memory:")
    connection.executescript(SCHEMA)
    for sid in ("session", "other"):
        connection.execute(
            "INSERT INTO sessions (id, created_at, demo_timestamp) VALUES (?, ?, ?)",
            (sid, "2026-10-22T09:00:00+05:30", "2026-10-22T09:00:00+05:30"),
        )
        seed_session(connection, sid)
    connection.commit()
    yield connection
    connection.close()


def snapshot(db):
    """Capture every committed domain table, including the other session."""
    return {table: [dict(row) for row in db.execute(f"SELECT * FROM {table}")]
            for table in ("sessions", "tasks", "calendar_blocks", "memory")}


def blocks(db):
    """Read the target session's blocks in time order."""
    return [{**{key: value for key, value in dict(row).items() if value is not None},
             "immutable": bool(row["immutable"])} for row in db.execute(
        "SELECT * FROM calendar_blocks WHERE session_id = ? ORDER BY start_time", ("session",)
    )]


def call(db, name, args):
    """Invoke a proposal through its registered schema and handler."""
    default_registry.validate_args(name, args)
    return default_registry.get(name).handler("session", args, db)


@pytest.mark.parametrize("fallback", [False, True])
def test_schedule(db, fallback):
    """Store validated caller blocks or the exact golden timetable and audit data."""
    before = snapshot(db)
    supplied = blocks(db)
    args = {"blocks": [] if fallback else supplied, "explanation": "Plan the day"}
    result = call(db, "propose_schedule", args)
    plan = dict(db.execute("SELECT * FROM plans WHERE id = ?", (result["plan_id"],)).fetchone())
    proposed = json.loads(plan["proposed_blocks"])
    if fallback:
        assert [(b["start_time"][11:16], b["end_time"][11:16]) for b in proposed] == [
            ("09:00", "09:05"), ("09:05", "10:00"), ("10:00", "10:30"),
            ("10:30", "11:15"), ("11:15", "12:15"), ("12:15", "13:00"),
            ("13:00", "14:00"), ("14:00", "14:45"), ("15:00", "16:00"), ("16:00", "17:00")]
    else:
        assert proposed == supplied
    assert plan["status"] == "PROPOSED"
    assert plan["state_version_at_proposal"] == result["state_version"] == 1
    assert plan["provider_used"] == "deterministic" and plan["degraded"] == 0
    assert plan["explanation"] == args["explanation"]
    assert plan["created_at"] == "2026-10-22T09:00:00+05:30"
    assert json.loads(plan["diff_summary"]) == result["diff"]
    log = dict(db.execute("SELECT * FROM execution_log").fetchone())
    assert log["plan_id"] == result["plan_id"] and log["tool_name"] == "propose_schedule"
    assert json.loads(log["tool_args"]) == args
    assert json.loads(log["tool_result"]) == result
    assert isinstance(log["duration_ms"], int) and log["duration_ms"] >= 0
    assert snapshot(db) == before


@pytest.mark.parametrize("protection", ["past", "completed"])
@pytest.mark.parametrize("mutation", ["none", "move", "shorten", "remove"])
def test_replan_protection(db, protection, mutation):
    """Past or completed mutable blocks must survive caller replans exactly."""
    db.execute("UPDATE calendar_blocks SET immutable = 0 WHERE session_id = ?", ("session",))
    if protection == "past":
        db.execute("UPDATE sessions SET demo_timestamp = ? WHERE id = ?",
                   ("2026-10-22T10:30:00+05:30", "session"))
    else:
        db.execute("UPDATE calendar_blocks SET status = 'completed' WHERE id = ?", (blocks(db)[0]["id"],))
    before = snapshot(db)
    supplied = blocks(db)
    if mutation == "move":
        supplied[0]["start_time"] = "2026-10-22T10:05:00+05:30"
    elif mutation == "shorten":
        supplied[0]["end_time"] = "2026-10-22T10:15:00+05:30"
    elif mutation == "remove":
        supplied.pop(0)
    supplied[-1].update(start_time="2026-10-22T13:30:00+05:30", end_time="2026-10-22T14:00:00+05:30")
    original = deepcopy(supplied)
    args = {"new_blocks": supplied, "explanation": "Adjust afternoon"}
    if mutation == "none":
        result = call(db, "propose_replan", args)
        assert len(result["diff"]["kept"]) == 1
        assert len(result["diff"]["moved"]) == 1
        assert result["diff"]["shortened"][0]["new_duration_min"] == 30
        assert json.loads(db.execute("SELECT proposed_blocks FROM plans").fetchone()[0]) == supplied
        assert db.execute("SELECT tool_name FROM execution_log").fetchone()[0] == "propose_replan"
    else:
        with pytest.raises(ValueError, match="Protected"):
            call(db, "propose_replan", args)
        assert db.execute("SELECT count(*) FROM plans").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM execution_log").fetchone()[0] == 0
    assert supplied == original
    assert snapshot(db) == before


@pytest.mark.parametrize("name,key", [("propose_schedule", "blocks"), ("propose_replan", "new_blocks")])
def test_overlap_rejected(db, name, key):
    """Invalid proposals create neither plans nor success log entries."""
    proposed = blocks(db)
    proposed[1]["start_time"] = proposed[0]["start_time"]
    before = snapshot(db)
    with pytest.raises(ValueError, match="overlap"):
        call(db, name, {key: proposed, "explanation": "Invalid"})
    assert db.execute("SELECT count(*) FROM plans").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM execution_log").fetchone()[0] == 0
    assert snapshot(db) == before


def test_empty_replan_does_not_generate(db):
    """Empty caller replans fail when they omit protected existing blocks."""
    with pytest.raises(ValueError, match="Protected"):
        call(db, "propose_replan", {"new_blocks": [], "explanation": ""})
    assert db.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_log_failure_rolls_back_plan(db):
    """An audit insert failure rolls back the proposal and preserves caller work."""
    db.execute("UPDATE sessions SET state_version = 7 WHERE id = 'session'")
    db.execute("CREATE TRIGGER reject_log BEFORE INSERT ON execution_log BEGIN SELECT RAISE(ABORT, 'log failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="log failure"):
        call(db, "propose_schedule", {"blocks": blocks(db), "explanation": ""})
    assert db.execute("SELECT count(*) FROM plans").fetchone()[0] == 0
    assert db.execute("SELECT state_version FROM sessions WHERE id = 'session'").fetchone()[0] == 7

