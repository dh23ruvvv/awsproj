"""Expose session-scoped data retrieval endpoints per Architecture §5.4."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.database import get_connection
from server.tools import read_tools

router = APIRouter()


class ScheduleResponse(BaseModel):
    """Represent committed schedule blocks and current state version."""

    blocks: list[dict]
    state_version: int


class TasksResponse(BaseModel):
    """Represent session tasks and current state version."""

    tasks: list[dict]
    state_version: int


class MemoryResponse(BaseModel):
    """Represent stored memory entries and current state version."""

    entries: list[dict]
    state_version: int


class ExecutionLogResponse(BaseModel):
    """Represent execution log entries."""

    entries: list[dict]


def _check_session(db, sid: str) -> JSONResponse | None:
    """Verify session exists before accessing data."""
    if db.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone() is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "SESSION_NOT_FOUND", "message": "Session not found", "details": {}}},
        )
    return None


@router.get("/sessions/{sid}/schedule", response_model=ScheduleResponse)
def get_schedule_data(sid: str):
    """Return committed calendar blocks chronologically with their state version."""
    db = get_connection()
    try:
        err = _check_session(db, sid)
        if err:
            return err
        return read_tools.get_schedule(sid, {}, db)
    finally:
        db.close()


@router.get("/sessions/{sid}/tasks", response_model=TasksResponse)
def get_tasks_data(sid: str):
    """Return session tasks and state version."""
    db = get_connection()
    try:
        err = _check_session(db, sid)
        if err:
            return err
        session = db.execute("SELECT state_version FROM sessions WHERE id = ?", (sid,)).fetchone()
        tasks_res = read_tools.get_tasks(sid, {}, db)
        return {"tasks": tasks_res["tasks"], "state_version": session["state_version"]}
    finally:
        db.close()


@router.get("/sessions/{sid}/memory", response_model=MemoryResponse)
def get_memory_data(sid: str):
    """Return memory entries belonging to the session and state version."""
    db = get_connection()
    try:
        err = _check_session(db, sid)
        if err:
            return err
        session = db.execute("SELECT state_version FROM sessions WHERE id = ?", (sid,)).fetchone()
        mem_res = read_tools.get_memory(sid, {}, db)
        return {"entries": mem_res["entries"], "state_version": session["state_version"]}
    finally:
        db.close()


@router.get("/sessions/{sid}/execution-log", response_model=ExecutionLogResponse)
def get_execution_log_data(sid: str):
    """Return execution log entries for the session."""
    db = get_connection()
    try:
        err = _check_session(db, sid)
        if err:
            return err
        rows = db.execute("SELECT * FROM execution_log WHERE session_id = ? ORDER BY created_at", (sid,))
        return {"entries": [dict(r) for r in rows]}
    finally:
        db.close()
