"""Versioned task editing without implicit calendar mutations."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from server.clock import now
from server.database import get_connection

router = APIRouter()


class TaskEdit(BaseModel):
    """Validate task updates and require an optimistic concurrency token."""

    state_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    duration_minutes: int | None = Field(default=None, ge=1, le=480)
    priority: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    category: Literal["work", "personal"] | None = None
    deadline: str | None = None
    status: Literal["pending", "completed", "cancelled"] | None = None

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        """Reject whitespace-only titles."""
        if value is not None and not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip() if value else value

    @field_validator("deadline")
    @classmethod
    def aware_deadline(cls, value):
        """Require an explicit timezone for a deadline."""
        if value is not None:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if "T" not in value or parsed.tzinfo is None:
                raise ValueError("Deadline must include date, time and timezone")
        return value


class TaskCreate(TaskEdit):
    """Require the essential task fields for creation."""

    title: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(ge=1, le=480)
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    category: Literal["work", "personal"] = "work"


def _mutate(sid, request, tid=None, delete=False):
    """Serialize task changes and stale all previously reviewed proposals."""
    db = get_connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if session is None:
            raise HTTPException(404, "Session not found")
        if session["state_version"] != request.state_version:
            raise HTTPException(409, "Workspace changed. Refresh and try again.")
        if tid:
            task = db.execute("SELECT * FROM tasks WHERE id=? AND session_id=?", (tid, sid)).fetchone()
            if task is None:
                raise HTTPException(404, "Task not found")
            if db.execute("SELECT 1 FROM calendar_blocks WHERE task_id=? AND session_id=?", (tid, sid)).fetchone():
                raise HTTPException(409, "This task is on the calendar. Its reviewed schedule is protected from direct edits.")
        values = request.model_dump(exclude_unset=True, exclude={"state_version"})
        if any(value is None for key, value in values.items() if key != "deadline"):
            raise HTTPException(422, "Only deadline may be cleared")
        if delete:
            db.execute("DELETE FROM tasks WHERE id=? AND session_id=?", (tid, sid))
        elif tid:
            if values:
                assignments = ",".join(f"{key}=?" for key in values)
                db.execute(f"UPDATE tasks SET {assignments} WHERE id=? AND session_id=?", (*values.values(), tid, sid))
        else:
            tid = str(uuid4())
            db.execute("INSERT INTO tasks (id,session_id,title,duration_minutes,priority,category,deadline,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (tid, sid, request.title, request.duration_minutes, request.priority, request.category,
                        request.deadline, request.status or "pending", now(session["demo_timestamp"])))
        db.execute("UPDATE sessions SET state_version=state_version+1 WHERE id=?", (sid,))
        db.execute("UPDATE plans SET status='STALE' WHERE session_id=? AND status='PROPOSED'", (sid,))
        result = {"state_version": session["state_version"] + 1}
        result.update({"deleted": True} if delete else {"task": dict(db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())})
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/sessions/{sid}/tasks", status_code=201)
def create_task(sid: str, request: TaskCreate):
    """Create a task without committing calendar changes."""
    return _mutate(sid, request)


@router.patch("/sessions/{sid}/tasks/{tid}")
def edit_task(sid: str, tid: str, request: TaskEdit):
    """Edit a task that has not yet been scheduled."""
    return _mutate(sid, request, tid)


@router.delete("/sessions/{sid}/tasks/{tid}")
def delete_task(sid: str, tid: str, request: TaskEdit):
    """Remove an unscheduled task using its owning session and version."""
    return _mutate(sid, request, tid, delete=True)
