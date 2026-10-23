"""Expose session-scoped data retrieval endpoints per Architecture §5.4."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.database import get_connection
from server.clock import now
from server.tools import read_tools
from server.tools.preferences import PreferenceInput, remember_preference

router = APIRouter()


class SessionInfoResponse(BaseModel):
    timestamp: str
    state_version: int
    pending_plan_id: str | None


@router.get('/sessions/{sid}/context', response_model=SessionInfoResponse)
def get_session_context(sid: str):
    db = get_connection()
    try:
        err = _check_session(db, sid)
        if err:
            return err
        session = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        plan = db.execute("SELECT id FROM plans WHERE session_id=? AND status='PROPOSED' ORDER BY created_at DESC LIMIT 1", (sid,)).fetchone()
        return {'timestamp': now(session['demo_timestamp']), 'state_version': session['state_version'], 'pending_plan_id': plan['id'] if plan else None}
    finally:
        db.close()


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


class PreferenceResponse(BaseModel):
    entry: dict
    state_version: int
    saved: bool


class DeletePreferenceResponse(BaseModel):
    deleted: bool
    state_version: int


@router.post('/sessions/{sid}/memory', response_model=PreferenceResponse, status_code=201)
def save_memory(sid: str, request: PreferenceInput):
    db = get_connection()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            err = _check_session(db, sid)
            if err:
                return err
            return remember_preference(sid, request.model_dump(), db)
    finally:
        db.close()


@router.delete('/sessions/{sid}/memory/{mid}', response_model=DeletePreferenceResponse)
def delete_memory(sid: str, mid: str):
    db = get_connection()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            err = _check_session(db, sid)
            if err:
                return err
            deleted = db.execute('DELETE FROM memory WHERE id=? AND session_id=?', (mid, sid))
            if not deleted.rowcount:
                raise HTTPException(404, 'Preference not found')
            db.execute('UPDATE sessions SET state_version=state_version+1 WHERE id=?', (sid,))
            return {'deleted': True, 'state_version': db.execute('SELECT state_version FROM sessions WHERE id=?', (sid,)).fetchone()[0]}
    finally:
        db.close()


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
