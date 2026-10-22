"""Personal day workspaces and idempotent weekday routine task generation."""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from server.database import get_connection

router = APIRouter()


class DayRequest(BaseModel):
    """Select a local calendar date and its UTC offset in minutes."""

    day: date
    offset_minutes: int = Field(ge=-720, le=840)


class RoutineTask(BaseModel):
    """A reusable task, without a calendar commitment or a fixed deadline."""

    title: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(ge=1, le=480)
    priority: Literal['HIGH', 'MEDIUM', 'LOW'] = 'MEDIUM'
    category: Literal['work', 'personal'] = 'personal'

    @field_validator('title')
    @classmethod
    def nonblank(cls, value):
        """Normalize titles and reject whitespace-only input."""
        if not value.strip():
            raise ValueError('A task needs a name')
        return value.strip()


class RoutineRequest(BaseModel):
    """Weekday numbers use Monday=0 through Sunday=6."""

    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    tasks: list[RoutineTask] = Field(min_length=1, max_length=30)
    starts_on: date

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        """Reject empty routine names."""
        if not value.strip():
            raise ValueError('A routine needs a name')
        return value.strip()

    @field_validator('weekdays')
    @classmethod
    def valid_days(cls, values):
        """Reject invalid or duplicate weekdays."""
        if any(v < 0 or v > 6 for v in values) or len(set(values)) != len(values):
            raise ValueError('Choose distinct weekdays from Monday through Sunday')
        return sorted(values)


def require_workspace(db, wid):
    """Keep every day and routine scoped to its owning workspace."""
    if not db.execute('SELECT 1 FROM workspaces WHERE id=?', (wid,)).fetchone():
        raise HTTPException(404, 'Workspace not found')


@router.post('/workspaces', status_code=201)
def create_workspace():
    """Create an empty personal workspace; never seed sample tasks."""
    wid = str(uuid4())
    db = get_connection()
    try:
        with db:
            db.execute('INSERT INTO workspaces VALUES (?,?)', (wid, datetime.now(timezone.utc).isoformat()))
        return {'workspace_id': wid}
    finally:
        db.close()


@router.post('/workspaces/{wid}/days')
def open_day(wid: str, request: DayRequest):
    """Open/create one isolated day and materialize matching routine tasks once.

    A pending proposal delays routine application until it is resolved, so merely
    opening a day cannot invalidate a plan the user is reviewing.
    """
    db = get_connection()
    try:
        db.execute('BEGIN IMMEDIATE')
        require_workspace(db, wid)
        day = request.day.isoformat()
        row = db.execute('SELECT session_id FROM workspace_days WHERE workspace_id=? AND day=?', (wid, day)).fetchone()
        if row:
            sid = row['session_id']
        else:
            sid = str(uuid4())
            stamp = datetime.combine(request.day, datetime.min.time().replace(hour=9), timezone(timedelta(minutes=request.offset_minutes))).isoformat()
            db.execute('INSERT INTO sessions (id,created_at,state_version,demo_timestamp,provider) VALUES (?,?,1,?,?)', (sid, datetime.now(timezone.utc).isoformat(), stamp, 'deterministic'))
            db.execute('INSERT INTO workspace_days VALUES (?,?,?)', (wid, day, sid))
        added = 0
        pending = db.execute("SELECT 1 FROM plans WHERE session_id=? AND status='PROPOSED'", (sid,)).fetchone()
        pending_tasks = db.execute("SELECT 1 FROM task_drafts WHERE session_id=? AND status='PROPOSED'", (sid,)).fetchone()
        if not pending and not pending_tasks:
            for routine in db.execute('SELECT * FROM routines WHERE workspace_id=? AND active=1 AND starts_on<=?', (wid, day)).fetchall():
                if request.day.weekday() not in json.loads(routine['weekdays']):
                    continue
                inserted = db.execute('INSERT OR IGNORE INTO routine_occurrences VALUES (?,?)', (routine['id'], sid)).rowcount
                if not inserted:
                    continue
                for task in json.loads(routine['tasks']):
                    db.execute('INSERT INTO tasks (id,session_id,title,duration_minutes,priority,category,status,created_at) VALUES (?,?,?,?,?,?,?,?)', (str(uuid4()), sid, task['title'], task['duration_minutes'], task['priority'], task['category'], 'pending', datetime.now(timezone.utc).isoformat()))
                    added += 1
            if added:
                db.execute('UPDATE sessions SET state_version=state_version+1 WHERE id=?', (sid,))
        session = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        db.commit()
        return {'session_id': sid, 'day': day, 'timestamp': session['demo_timestamp'], 'state_version': session['state_version'], 'routine_tasks_added': added}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get('/workspaces/{wid}/routines')
def list_routines(wid: str):
    """List active routines for the personal workspace."""
    db = get_connection()
    try:
        require_workspace(db, wid)
        return {'routines': [{**dict(r), 'weekdays': json.loads(r['weekdays']), 'tasks': json.loads(r['tasks'])} for r in db.execute('SELECT * FROM routines WHERE workspace_id=? AND active=1 ORDER BY rowid', (wid,))]}
    finally:
        db.close()


@router.post('/workspaces/{wid}/routines', status_code=201)
def create_routine(wid: str, request: RoutineRequest):
    """Save an explicitly requested recurrence; apply when a matching day opens."""
    db = get_connection()
    try:
        with db:
            require_workspace(db, wid)
            rid = str(uuid4())
            db.execute('INSERT INTO routines (id,workspace_id,name,weekdays,tasks,starts_on) VALUES (?,?,?,?,?,?)', (rid, wid, request.name, json.dumps(request.weekdays), json.dumps([t.model_dump() for t in request.tasks]), request.starts_on.isoformat()))
        return {'id': rid}
    finally:
        db.close()


@router.delete('/workspaces/{wid}/routines/{rid}')
def stop_routine(wid: str, rid: str):
    """Stop future generation while preserving already created tasks and history."""
    db = get_connection()
    try:
        with db:
            require_workspace(db, wid)
            if not db.execute('UPDATE routines SET active=0 WHERE id=? AND workspace_id=? AND active=1', (rid, wid)).rowcount:
                raise HTTPException(404, 'Routine not found')
        return {'stopped': True}
    finally:
        db.close()
