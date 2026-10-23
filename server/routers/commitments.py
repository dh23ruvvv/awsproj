"""Propose fixed calendar commitments through the normal approval lifecycle."""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from server.clock import now
from server.database import get_connection
from server.engine.scheduler import compute_replan
from server.engine.validator import _time, validate_schedule
from server.routers.plans import PlanResponse
from server.tools.propose_tools import propose_replan

router = APIRouter()


class CommitmentRequest(BaseModel):
    """Describe a fixed event without directly writing the calendar."""

    title: str = Field(min_length=1, max_length=200)
    start_time: str
    end_time: str
    state_version: int = Field(ge=1)


@router.post("/sessions/{sid}/commitments", response_model=PlanResponse)
def propose_commitment(sid: str, request: CommitmentRequest):
    """Review any required moves before saving a protected commitment."""
    db = get_connection()
    try:
        db.execute("BEGIN IMMEDIATE")
        session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if session is None:
            raise HTTPException(404, "Session not found")
        if request.state_version != session["state_version"]:
            raise HTTPException(409, "Workspace changed. Refresh and try again.")
        if not request.title.strip():
            raise HTTPException(422, "Commitment title cannot be blank")

        # Validate timestamp structure and ordering
        try:
            start, end = _time(request.start_time), _time(request.end_time)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, f"Invalid event timestamp: {exc}") from exc

        if start.tzinfo is None or end.tzinfo is None or start.utcoffset() is None or end.utcoffset() is None:
            raise HTTPException(422, "Timestamps must include a timezone offset")
        if start >= end:
            raise HTTPException(422, "End time must be later than start time")

        existing = [dict(row) for row in db.execute("SELECT * FROM calendar_blocks WHERE session_id=?", (sid,))]
        event = request.model_dump(exclude={"state_version"})
        event["title"] = event["title"].strip()
        event["immutable"] = True

        # Check for overlap with existing protected / completed blocks
        for block in existing:
            b_start, b_end = _time(block["start_time"]), _time(block["end_time"])
            protected = block.get("immutable") or str(block.get("status", "")).lower() == "completed"
            if protected and start < b_end and b_start < end:
                raise HTTPException(
                    422,
                    f"Cannot add '{event['title']}': overlaps with protected event '{block['title']}' "
                    f"({block['start_time'][11:16]}–{block['end_time'][11:16]})."
                )

        # Check for overlap with movable scheduled tasks
        overlapping_movables = [
            b for b in existing
            if not (b.get("immutable") or str(b.get("status", "")).lower() == "completed")
            and start < _time(b["end_time"]) and _time(b["start_time"]) < end
        ]

        current_clock = now(session["demo_timestamp"])

        if not overlapping_movables:
            # When there are no collisions with movable tasks, keep existing blocks untouched
            blocks = sorted(existing + [event], key=lambda b: _time(b["start_time"]))
            explanation = f"Added fixed event '{event['title']}' ({event['start_time'][11:16]}–{event['end_time'][11:16]}). Existing schedule is preserved."
        else:
            # Try to replan colliding movable tasks around the new commitment
            try:
                tasks = [dict(row) for row in db.execute('SELECT * FROM tasks WHERE session_id=?', (sid,))]
                blocks = compute_replan(existing, event, current_clock, tasks=tasks)
                explanation = f"Review the new fixed commitment '{event['title']}' and any moved tasks. Confirm to save."
            except ValueError:
                # If movable tasks cannot be rescheduled within working hours, displace them to pending
                displaced_tasks = {b.get('task_id') for b in overlapping_movables if b.get('task_id')}
                blocks = sorted([b for b in existing if b not in overlapping_movables and b.get('task_id') not in displaced_tasks] + [event], key=lambda b: _time(b["start_time"]))
                titles = ", ".join(f"'{b['title']}'" for b in overlapping_movables)
                explanation = f"Added fixed event '{event['title']}'. Displaced {titles} and returned to your task list."

        errors = validate_schedule(blocks, existing, current_clock)
        if errors:
            raise HTTPException(422, "; ".join(errors))

        result = propose_replan(sid, {"new_blocks": blocks, "explanation": explanation}, db)
        plan = db.execute("SELECT * FROM plans WHERE id=?", (result["plan_id"],)).fetchone()
        db.commit()
        return dict(
            plan_id=plan["id"],
            status=plan["status"],
            proposed_blocks=json.loads(plan["proposed_blocks"]),
            diff=json.loads(plan["diff_summary"]),
            explanation=plan["explanation"],
            state_version_at_proposal=plan["state_version_at_proposal"],
            provider_used="deterministic",
            degraded=False,
        )
    except (ValueError, TypeError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    finally:
        db.close()
