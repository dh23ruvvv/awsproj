"""Validate task edits and persist reviewable drafts, without mutating tasks."""
import json
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from server.routers.tasks import TaskCreate


class TaskChange(BaseModel):
    """Updates inherit omitted fields; removals only need the task ID."""
    model_config = ConfigDict(extra='forbid')
    action: Literal['add', 'update', 'remove']
    task_id: str | None = None
    title: str | None = None
    duration_minutes: int | None = None
    priority: Literal['HIGH', 'MEDIUM', 'LOW'] | None = None
    category: Literal['work', 'personal'] | None = None
    deadline: str | None = None


class TaskDraftInput(BaseModel):
    """Bound the number of changes offered for one human review."""
    model_config = ConfigDict(extra='forbid')
    changes: list[TaskChange] = Field(min_length=1, max_length=20)
    explanation: str = Field(min_length=1, max_length=500)


def validate_changes(db, sid, changes):
    """Resolve ownership, protect scheduled work, and validate all fields first."""
    normalized, seen = [], set()
    for raw in changes:
        change = TaskChange.model_validate(raw)
        before = None
        if change.action != 'add':
            if not change.task_id or change.task_id in seen:
                raise ValueError('Each existing task must have one distinct task ID')
            seen.add(change.task_id)
            row = db.execute('SELECT * FROM tasks WHERE id=? AND session_id=?', (change.task_id, sid)).fetchone()
            if not row:
                raise ValueError('Task does not belong to this day')
            if row['status'] != 'pending' or db.execute('SELECT 1 FROM calendar_blocks WHERE task_id=? AND session_id=?', (change.task_id, sid)).fetchone():
                raise ValueError('Scheduled or completed tasks are protected. Use a schedule proposal for calendar changes.')
            before = dict(row)
        elif change.task_id:
            raise ValueError('New tasks must not supply an existing task ID')
        after = None
        if change.action != 'remove':
            supplied = change.model_fields_set
            title = change.title if change.title is not None else (before['title'] if before else None)
            duration = change.duration_minutes if change.duration_minutes is not None else (before['duration_minutes'] if before else None)
            priority = change.priority or (before['priority'] if before else 'MEDIUM')
            category = change.category or (before['category'] if before else 'work')
            deadline = change.deadline if 'deadline' in supplied or not before else before['deadline']
            validated = TaskCreate(state_version=1, title=title, duration_minutes=duration,
                                   priority=priority, category=category, deadline=deadline)
            after = validated.model_dump(include={'title', 'duration_minutes', 'priority', 'category', 'deadline'})
        normalized.append({'action': change.action, 'task_id': change.task_id, 'before': before, 'after': after})
    return normalized


def propose_task_changes(session_id, args, db_conn):
    """Offer a validated batch for review; human confirmation is a separate route."""
    request = TaskDraftInput.model_validate(args)
    session = db_conn.execute('SELECT state_version FROM sessions WHERE id=?', (session_id,)).fetchone()
    if session is None:
        raise ValueError('Session does not exist')
    if db_conn.execute("SELECT 1 FROM plans WHERE session_id=? AND status='PROPOSED'", (session_id,)).fetchone():
        raise ValueError('Finish reviewing the calendar proposal before changing tasks')
    if db_conn.execute("SELECT 1 FROM task_drafts WHERE session_id=? AND status='PROPOSED'", (session_id,)).fetchone():
        raise ValueError('Finish reviewing the existing task changes first')
    raw = [c.model_dump(exclude_unset=True) for c in request.changes]
    changes = validate_changes(db_conn, session_id, raw)
    draft_id = str(uuid4())
    db_conn.execute('INSERT INTO task_drafts (id,session_id,state_version,status,changes,raw_changes,explanation) VALUES (?,?,?,?,?,?,?)',
                    (draft_id, session_id, session['state_version'], 'PROPOSED', json.dumps(changes), json.dumps(raw), request.explanation))
    return {'task_draft_id': draft_id, 'changes': changes, 'state_version': session['state_version'], 'instruction': 'These changes are NOT saved. Ask the user to review and confirm. Schedule only after task confirmation in a later turn.'}
