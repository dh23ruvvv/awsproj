"""Validate task ownership, deadlines and complete allocated durations."""

from collections import defaultdict
from server.engine.validator import _time
from server.clock import now


def validate_task_allocations(db, sid, blocks):
    """Return errors rather than silently accepting truncated task allocations."""
    totals = defaultdict(float)
    errors = []
    session = db.execute("SELECT demo_timestamp FROM sessions WHERE id=?", (sid,)).fetchone()
    current = _time(now(session["demo_timestamp"]))
    day_start = current.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = current.replace(hour=17, minute=0, second=0, microsecond=0)
    tasks = {row["id"]: dict(row) for row in db.execute("SELECT * FROM tasks WHERE session_id=?", (sid,))}
    for block in blocks:
        tid = block.get("task_id")
        if not tid:
            continue
        task = tasks.get(tid)
        if task is None:
            errors.append("Task does not belong to session")
            continue
        start, end = _time(block["start_time"]), _time(block["end_time"])
        if not block.get("immutable") and block.get("status") != "completed" and (start < day_start or end > day_end):
            errors.append(f"{task['title']} must fit within the 09:00–17:00 workday.")
        totals[tid] += (end - start).total_seconds() / 60
        if task["deadline"] and end > _time(task["deadline"]):
            errors.append(f"{task['title']} exceeds its deadline; shorten the task estimate or choose another day.")
    for tid, minutes in totals.items():
        if minutes != tasks[tid]["duration_minutes"]:
            errors.append(f"{tasks[tid]['title']} needs exactly {tasks[tid]['duration_minutes']} minutes; proposal allocates {minutes:g}.")
    return errors
