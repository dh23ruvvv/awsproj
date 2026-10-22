"""Human-only confirmation of versioned task batches, atomically and once."""
import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from server.clock import now
from server.database import get_connection
from server.tools.task_drafts import validate_changes

router = APIRouter()


class TaskDraftConfirmation(BaseModel):
    """Bind approval to the version that was actually reviewed."""
    state_version: int = Field(ge=1)


def find(db, sid, did):
    """Scope draft lookup to its owning session."""
    row = db.execute('SELECT * FROM task_drafts WHERE id=? AND session_id=?', (did, sid)).fetchone()
    if not row:
        raise HTTPException(404, 'Task draft not found')
    return row


def view(row):
    """Expose only review fields, without internal normalization metadata."""
    return {'id': row['id'], 'status': row['status'], 'state_version': row['state_version'], 'explanation': row['explanation'], 'changes': json.loads(row['changes'])}


@router.get('/sessions/{sid}/task-drafts/pending')
def pending(sid: str):
    """Recover a task review after refresh, without relying on browser cache."""
    db = get_connection()
    try:
        row = db.execute("SELECT * FROM task_drafts WHERE session_id=? AND status='PROPOSED' ORDER BY rowid DESC LIMIT 1", (sid,)).fetchone()
        return {'draft': view(row) if row else None}
    finally:
        db.close()


@router.get('/sessions/{sid}/task-drafts/{did}')
def get_draft(sid: str, did: str):
    """Retrieve an immutable review snapshot."""
    db = get_connection()
    try:
        return view(find(db, sid, did))
    finally:
        db.close()


@router.post('/sessions/{sid}/task-drafts/{did}/confirm')
def confirm(sid: str, did: str, request: TaskDraftConfirmation):
    """Revalidate a batch and apply all or none; retries cannot duplicate tasks."""
    db = get_connection()
    try:
        db.execute('BEGIN IMMEDIATE')
        draft = find(db, sid, did)
        session = db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        if draft['status'] == 'CONFIRMED':
            return {'state_version': session['state_version'], 'already_confirmed': True}
        if draft['status'] != 'PROPOSED':
            raise HTTPException(409, 'This task draft is no longer awaiting approval')
        if request.state_version != draft['state_version'] or session['state_version'] != draft['state_version']:
            raise HTTPException(409, 'Your tasks changed. Cancel this draft, refresh, and ask again.')
        changes = validate_changes(db, sid, json.loads(draft['raw_changes']))
        for change in changes:
            after, tid = change['after'], change['task_id']
            if change['action'] == 'remove':
                db.execute('DELETE FROM tasks WHERE id=? AND session_id=?', (tid, sid))
            elif change['action'] == 'update':
                db.execute('UPDATE tasks SET title=?,duration_minutes=?,priority=?,category=?,deadline=? WHERE id=? AND session_id=?',
                           (after['title'], after['duration_minutes'], after['priority'], after['category'], after['deadline'], tid, sid))
            else:
                db.execute('INSERT INTO tasks (id,session_id,title,duration_minutes,priority,category,deadline,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                           (str(uuid4()), sid, after['title'], after['duration_minutes'], after['priority'], after['category'], after['deadline'], 'pending', now(session['demo_timestamp'])))
        db.execute('UPDATE sessions SET state_version=state_version+1 WHERE id=?', (sid,))
        db.execute("UPDATE task_drafts SET status='CONFIRMED' WHERE id=?", (did,))
        db.execute("UPDATE plans SET status='STALE' WHERE session_id=? AND status='PROPOSED'", (sid,))
        db.commit()
        return {'state_version': session['state_version'] + 1, 'already_confirmed': False}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post('/sessions/{sid}/task-drafts/{did}/cancel')
def cancel(sid: str, did: str):
    """Discard a draft without changing tasks or the calendar."""
    db = get_connection()
    try:
        with db:
            draft = find(db, sid, did)
            if draft['status'] == 'CONFIRMED':
                raise HTTPException(409, 'This task draft has already been confirmed')
            db.execute("UPDATE task_drafts SET status='CANCELLED' WHERE id=?", (did,))
        return {'cancelled': True}
    finally:
        db.close()
