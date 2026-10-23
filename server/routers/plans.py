"""Expose session-scoped plan lifecycle endpoints."""

import json

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.database import get_connection
from server.tools.commit_tools import PlanError, commit_schedule, find_plan

router = APIRouter()


class ConfirmRequest(BaseModel):
    """Accept an optional version defaulting to the proposal snapshot."""

    state_version: int | None = None


class PlanResponse(BaseModel):
    """Represent the documented Plan details response."""

    plan_id: str
    status: str
    proposed_blocks: list[dict]
    diff: dict | None = None
    explanation: str | None = None
    state_version_at_proposal: int
    provider_used: str
    degraded: bool


class ConfirmResponse(BaseModel):
    """Represent the documented Confirm plan response."""

    committed: bool
    state_version: int
    already_executed: bool = False
    execution_log: list[dict] | None = None


class CancelResponse(BaseModel):
    """Represent the documented Cancel plan response."""

    cancelled: bool
    state_version: int


@router.get("/sessions/{sid}/plans/{pid}", response_model=PlanResponse)
def get_plan(sid: str, pid: str):
    """Return persisted plan details."""
    db = get_connection()
    try:
        plan = find_plan(db, sid, pid)
        return dict(plan_id=pid, status=plan["status"],
                    proposed_blocks=json.loads(plan["proposed_blocks"]),
                    diff=json.loads(plan["diff_summary"]) if plan["diff_summary"] else None,
                    explanation=plan["explanation"],
                    state_version_at_proposal=plan["state_version_at_proposal"],
                    provider_used=plan["provider_used"], degraded=bool(plan["degraded"]))
    except PlanError as exc:
        return JSONResponse(status_code=exc.status, content=exc.payload)
    finally:
        db.close()


@router.post("/sessions/{sid}/plans/{pid}/confirm", response_model=ConfirmResponse, response_model_exclude_none=True)
def confirm_plan(sid: str, pid: str, request: ConfirmRequest = Body(default_factory=ConfirmRequest)):
    """Execute the registered commit implementation."""
    db = get_connection()
    try:
        args = {"plan_id": pid}
        if request.state_version is not None:
            args["state_version"] = request.state_version
        return commit_schedule(sid, args, db)
    except PlanError as exc:
        return JSONResponse(status_code=exc.status, content=exc.payload)
    finally:
        db.close()


@router.post("/sessions/{sid}/plans/{pid}/cancel", response_model=CancelResponse)
def cancel_plan(sid: str, pid: str):
    """Cancel proposed plans without altering domain state."""
    db = get_connection()
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            find_plan(db, sid, pid)
            cursor = db.execute("UPDATE plans SET status='CANCELLED' WHERE id=? AND session_id=? AND status='PROPOSED'", (pid, sid))
            if cursor.rowcount != 1:
                raise PlanError(409, "PLAN_NOT_PROPOSED", "This plan is no longer awaiting approval")
            version = db.execute("SELECT state_version FROM sessions WHERE id=?", (sid,)).fetchone()[0]
        return {"cancelled": True, "state_version": version}
    except PlanError as exc:
        return JSONResponse(status_code=exc.status, content=exc.payload)
    finally:
        db.close()

