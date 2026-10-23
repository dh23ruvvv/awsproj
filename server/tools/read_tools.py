"""Read session-scoped scheduling data without mutating persisted state."""

from sqlite3 import Connection

from server.clock import now


def get_tasks(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Return session tasks, optionally restricted to the requested status."""
    query = "SELECT * FROM tasks WHERE session_id = ?"
    parameters = [session_id]
    if args.get("status"):
        query += " AND status = ?"
        parameters.append(args["status"])
    return {"tasks": [dict(row) for row in db_conn.execute(query, parameters)]}


def get_calendar(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Return session calendar blocks, optionally matching a literal date prefix."""
    query = "SELECT * FROM calendar_blocks WHERE session_id = ?"
    parameters = [session_id]
    if args.get("date"):
        query += " AND substr(start_time, 1, length(?)) = ?"
        parameters.extend([args["date"], args["date"]])
    return {"blocks": [dict(row, immutable=bool(row['immutable'])) for row in db_conn.execute(query, parameters)]}


def get_current_time(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Return the session's injectable clock and configured display timezone."""
    session = db_conn.execute(
        "SELECT demo_timestamp FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return {"current_time": now(session["demo_timestamp"]), "timezone": "Asia/Kolkata"}


def get_schedule(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Return committed calendar blocks chronologically with their state version."""
    session = db_conn.execute(
        "SELECT state_version FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    rows = db_conn.execute(
        "SELECT * FROM calendar_blocks WHERE session_id = ? ORDER BY start_time",
        (session_id,),
    )
    return {"blocks": [dict(row, immutable=bool(row['immutable'])) for row in rows], "state_version": session["state_version"]}


def get_memory(session_id: str, args: dict, db_conn: Connection) -> dict:
    """Return memory entries belonging to the current session."""
    rows = db_conn.execute("SELECT * FROM memory WHERE session_id = ?", (session_id,))
    return {"entries": [dict(row) for row in rows]}
