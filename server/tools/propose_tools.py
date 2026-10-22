"""Validate and persist draft schedules without changing committed domain state."""

import json
from sqlite3 import Connection
from time import perf_counter
from uuid import uuid4

from server.clock import now
from server.engine.scheduler import compute_day_schedule
from server.engine.validator import validate_schedule, inherit_block_metadata
from server.engine.differ import compute_diff
from server.engine.task_validation import validate_task_allocations


def _propose(session_id: str, args: dict, db_conn: Connection, replan: bool) -> dict:
    """Validate a proposal and atomically store its plan and execution record."""
    started = perf_counter()
    session = db_conn.execute(
        "SELECT demo_timestamp, state_version FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise ValueError("Session does not exist")
    current_time = now(session["demo_timestamp"])
    existing = [dict(row) for row in db_conn.execute(
        "SELECT * FROM calendar_blocks WHERE session_id = ? ORDER BY start_time", (session_id,)
    )]
    if replan:
        blocks = args.get("new_blocks", [])
    else:
        blocks = args.get("blocks")
        if not blocks:
            tasks = [dict(row) for row in db_conn.execute(
                "SELECT * FROM tasks WHERE session_id = ?", (session_id,)
            )]
            blocks = compute_day_schedule(tasks, existing, current_time)
    blocks = inherit_block_metadata(blocks, existing)
    errors = validate_schedule(blocks, existing, current_time)
    if errors:
        raise ValueError("; ".join(errors))
    errors = validate_task_allocations(db_conn, session_id, blocks)
    if errors:
        raise ValueError("; ".join(errors))
    diff = compute_diff(existing, blocks)
    plan_id = str(uuid4())
    result = {"plan_id": plan_id, "diff": diff, "state_version": session["state_version"]}
    tool_name = "propose_replan" if replan else "propose_schedule"
    db_conn.execute("SAVEPOINT propose_tool")
    try:
        db_conn.execute(
            "UPDATE plans SET status = 'CANCELLED' WHERE session_id = ? AND status = 'PROPOSED'",
            (session_id,)
        )
        db_conn.execute(
            "INSERT INTO plans (id, session_id, status, proposed_blocks, diff_summary, explanation, "
            "state_version_at_proposal, provider_used, degraded, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, session_id, "PROPOSED", json.dumps(blocks), json.dumps(diff),
             args.get("explanation", ""), session["state_version"],
             args.get("provider_used", "deterministic"), 0, current_time),
        )
        db_conn.execute(
            "INSERT INTO execution_log (id, session_id, plan_id, tool_name, tool_args, "
            "tool_result, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), session_id, plan_id, tool_name, json.dumps(args), json.dumps(result),
             int((perf_counter() - started) * 1000), now(session["demo_timestamp"])),
        )
        db_conn.execute("RELEASE SAVEPOINT propose_tool")
    except Exception:
        db_conn.execute("ROLLBACK TO SAVEPOINT propose_tool")
        db_conn.execute("RELEASE SAVEPOINT propose_tool")
        raise
    return result


def propose_schedule(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Propose caller blocks, computing a day schedule when blocks are empty."""
    return _propose(session_id, args, db_conn, replan=False)


def propose_replan(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Propose caller changes while preserving completed and elapsed blocks."""
    return _propose(session_id, args, db_conn, replan=True)
