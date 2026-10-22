"""Commit session-owned plans atomically with durable outcome logging."""

import json
from sqlite3 import Connection
from time import perf_counter
from uuid import uuid4

from server.clock import now
from server.engine.validator import validate_schedule, inherit_block_metadata
from server.engine.task_validation import validate_task_allocations


class PlanError(Exception):
    """Represent a public lifecycle error."""

    def __init__(self, status, code, message, details=None):
        """Store the status and API envelope."""
        super().__init__(message)
        self.status = status
        self.payload = {"error": {"code": code, "message": message, "details": details or {}}}


def find_plan(db, sid, pid):
    """Look up a plan within its owning session."""
    row = db.execute("SELECT * FROM plans WHERE id=? AND session_id=?", (pid, sid)).fetchone()
    if row is None:
        raise PlanError(404, "PLAN_NOT_FOUND", "Plan not found")
    return row


def commit_schedule(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Serialize confirmation and commit domain changes or a failure outcome."""
    owned = not db_conn.in_transaction
    if owned:
        db_conn.execute("BEGIN IMMEDIATE")
    try:
        result = _commit(session_id, args, db_conn, owned)
    except PlanError:
        if owned:
            db_conn.commit()
        raise
    except Exception:
        if owned:
            db_conn.rollback()
        raise
    else:
        if owned:
            db_conn.commit()
        return result


def _commit(sid, args, db, owned):
    """Guard the plan version and execute mutations inside a savepoint."""
    started = perf_counter()
    pid = args["plan_id"]
    plan = find_plan(db, sid, pid)
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    version = session["state_version"]
    if plan["status"] == "EXECUTED":
        return {"committed": True, "state_version": version, "already_executed": True}
    if plan["status"] != "PROPOSED":
        raise PlanError(409, "INVALID_PLAN_STATE", "Plan is not in PROPOSED state", {"status": plan["status"]})
    if args.get("state_version", plan["state_version_at_proposal"]) != version or plan["state_version_at_proposal"] != version:
        db.execute("UPDATE plans SET status='STALE' WHERE id=?", (pid,))
        raise PlanError(409, "STALE_PLAN", "Plan state_version does not match current session state.",
                        {"expected": plan["state_version_at_proposal"], "current": version})
    timestamp = now(session["demo_timestamp"])
    db.execute("SAVEPOINT commit_domain")
    try:
        blocks = json.loads(plan["proposed_blocks"])
        existing = [dict(row) for row in db.execute("SELECT * FROM calendar_blocks WHERE session_id=?", (sid,))]
        blocks = inherit_block_metadata(blocks, existing)
        errors = validate_schedule(blocks, existing, timestamp)
        if not errors:
            errors = validate_task_allocations(db, sid, blocks)
        if errors:
            raise ValueError("; ".join(errors))
        db.execute("UPDATE plans SET status='CONFIRMED', confirmed_at=? WHERE id=?", (timestamp, pid))
        db.execute("UPDATE plans SET status='EXECUTING' WHERE id=?", (pid,))
        retained = set()
        for block in blocks:
            task = block.get("task_id")
            if task and db.execute("SELECT 1 FROM tasks WHERE id=? AND session_id=?", (task, sid)).fetchone() is None:
                raise ValueError("Task does not belong to session")
            bid = block.get("id")
            old = None
            if bid:
                old = db.execute("SELECT * FROM calendar_blocks WHERE id=?", (bid,)).fetchone()
            else:
                if task:
                    query = f"SELECT * FROM calendar_blocks WHERE session_id=? AND task_id=?" + (
                        f" AND id NOT IN ({','.join('?' * len(retained))})" if retained else ""
                    )
                    params = (sid, task, *retained) if retained else (sid, task)
                    old = db.execute(query, params).fetchone()
                if old is None and block.get("title"):
                    query = f"SELECT * FROM calendar_blocks WHERE session_id=? AND title=?" + (
                        f" AND id NOT IN ({','.join('?' * len(retained))})" if retained else ""
                    )
                    params = (sid, block["title"], *retained) if retained else (sid, block["title"])
                    old = db.execute(query, params).fetchone()
                bid = old["id"] if old is not None else str(uuid4())
            if old is not None and old["session_id"] != sid:
                raise ValueError("Block does not belong to session")
            retained.add(bid)
            if old is not None and old["status"] == "completed":
                continue
            values = (block["title"], block["start_time"], block["end_time"], int(block.get("immutable", False)),
                      task, block.get("status", "scheduled"), pid)
            if old is None:
                db.execute("INSERT INTO calendar_blocks (title,start_time,end_time,immutable,task_id,status,plan_id,id,session_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (*values, bid, sid, timestamp))
            else:
                db.execute("UPDATE calendar_blocks SET title=?,start_time=?,end_time=?,immutable=?,task_id=?,status=?,plan_id=? WHERE id=? AND session_id=?",
                           (*values, bid, sid))
            if task:
                db.execute("UPDATE tasks SET status='scheduled' WHERE id=? AND session_id=? AND status='pending'", (task, sid))
        for row in db.execute("SELECT id FROM calendar_blocks WHERE session_id=? AND status != 'completed'", (sid,)).fetchall():
            if row["id"] not in retained:
                db.execute("DELETE FROM calendar_blocks WHERE id=? AND session_id=?", (row["id"], sid))
        db.execute("UPDATE tasks SET status='pending' WHERE session_id=? AND status='scheduled' AND NOT EXISTS (SELECT 1 FROM calendar_blocks WHERE calendar_blocks.task_id=tasks.id)", (sid,))
        db.execute("UPDATE sessions SET state_version=state_version+1 WHERE id=?", (sid,))
        db.execute("UPDATE plans SET status='EXECUTED',executed_at=? WHERE id=?", (timestamp, pid))
        result = {"committed": True, "state_version": version + 1}
        log = _log(db, sid, pid, args, result, started, timestamp)
        db.execute("RELEASE SAVEPOINT commit_domain")
        return {**result, "execution_log": [log]}
    except Exception as exc:
        db.execute("ROLLBACK TO SAVEPOINT commit_domain")
        db.execute("RELEASE SAVEPOINT commit_domain")
        if owned:
            db.rollback()
            db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE plans SET status='FAILED' WHERE id=?", (pid,))
        _log(db, sid, pid, args, {"committed": False, "error": str(exc)}, started, timestamp)
        raise PlanError(500, "COMMIT_FAILED", "Plan execution failed") from exc


def _log(db, sid, pid, args, result, started, timestamp):
    """Write the execution outcome after success or domain rollback."""
    entry = dict(id=str(uuid4()), session_id=sid, plan_id=pid, tool_name="commit_schedule",
                 tool_args=json.dumps(args), tool_result=json.dumps(result),
                 duration_ms=int((perf_counter() - started) * 1000), created_at=timestamp)
    db.execute("INSERT INTO execution_log (id,session_id,plan_id,tool_name,tool_args,tool_result,duration_ms,created_at) VALUES (?,?,?,?,?,?,?,?)", tuple(entry.values()))
    return entry
