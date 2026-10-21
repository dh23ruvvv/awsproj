"""Deterministic day planning with focus, personal, and overflow reservations.

The timetable policy uses a five-minute planning period, focus reservations
of 55/60/45 minutes, a 45-minute personal slot, and afternoon errands.
Reservations may exceed estimates, as required by the pinned demo timetable.
"""

from copy import deepcopy
from datetime import timedelta

from .validator import _time, validate_schedule


def compute_day_schedule(tasks, calendar_blocks, current_time):
    """Allocate tasks by priority into the day policy, preserving calendar blocks.

Raise ValueError when the policy cannot accommodate a task before its deadline
or within the working day rather than returning an invalid partial schedule.
"""
    now = _time(current_time)
    origin = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = origin + timedelta(hours=8)
    blocks = deepcopy(calendar_blocks)
    assigned = {block.get("task_id") for block in blocks}
    pending = [task for task in tasks if task["id"] not in assigned and
               task.get("status", "pending").lower() not in ("completed", "cancelled")]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    pending.sort(key=lambda task: (rank.get(task.get("priority", "LOW").upper(), 2),
                                   task.get("deadline") or "9999"))

    def place(title, offset, minutes, task=None):
        """Place one reservation at or after its preferred time in a free slot."""
        start = max(origin + timedelta(minutes=offset), now)
        duration = timedelta(minutes=minutes)
        for block in sorted(blocks, key=lambda item: _time(item["start_time"])):
            left, right = _time(block["start_time"]), _time(block["end_time"])
            if start < right and start + duration > left:
                start = right
        end = start + duration
        if end > day_end or (task and task.get("deadline") and end > _time(task["deadline"])):
            raise ValueError(f"Cannot schedule {title} within day/deadline")
        block = {"title": title, "start_time": start.isoformat(), "end_time": end.isoformat(), "immutable": False}
        if task:
            block["task_id"] = task["id"]
        blocks.append(block)

    place("Planning", 0, 5)
    focus = next((task for task in pending if task.get("category") == "work" and task["duration_minutes"] > 60), None)
    if focus:
        pending.remove(focus)
        remaining = focus["duration_minutes"]
        for part, (offset, reservation) in enumerate(((5, 55), (135, 60), (300, 45)), 1):
            if remaining <= 0:
                break
            place(f"{focus['title']} (part {part})", offset, reservation, focus)
            remaining -= reservation
        if remaining > 0:
            raise ValueError("Focus task exceeds available reservations")
    for task in pending:
        personal = task.get("category") == "personal"
        low = task.get("priority", "").upper() == "LOW"
        offset = 360 if personal and low else 195 if personal else 90
        duration = min(task["duration_minutes"], 45) if personal and not low else task["duration_minutes"]
        place(task["title"], offset, duration, task)
    place("Buffer / overflow", 420, 60)
    blocks.sort(key=lambda block: _time(block["start_time"]))
    errors = validate_schedule(blocks, calendar_blocks, current_time)
    if errors:
        raise ValueError("; ".join(errors))
    return blocks


def compute_replan(current_blocks, interruption, current_time):
    """Insert an interruption, shift future work, and consume overflow slack."""
    now = _time(current_time)
    blocks = []
    for original in current_blocks:
        block = deepcopy(original)
        if block["title"] == "Planning" and _time(block["end_time"]) <= now:
            continue
        if _time(block["end_time"]) <= now:
            block["status"] = "completed"
            block["immutable"] = True
        blocks.append(block)
    meeting = deepcopy(interruption)
    start, end = _time(meeting["start_time"]), _time(meeting["end_time"])
    if start < now or end <= start:
        raise ValueError("Interruption must be a future positive interval")
    for block in blocks:
        if (block.get("immutable") or _time(block["start_time"]) < now) and start < _time(block["end_time"]) and _time(block["start_time"]) < end:
            raise ValueError("Interruption overlaps protected or in-progress block")
    cursor = end
    for block in sorted(blocks, key=lambda item: _time(item["start_time"])):
        left, right = _time(block["start_time"]), _time(block["end_time"])
        if right <= start:
            continue
        if block.get("immutable"):
            if left < cursor:
                raise ValueError("Replan collides with immutable block")
            cursor = right
            continue
        shifted = max(left, cursor)
        finish = right if block["title"] == "Buffer / overflow" else shifted + (right - left)
        if finish <= shifted:
            continue
        block["start_time"], block["end_time"] = shifted.isoformat(), finish.isoformat()
        cursor = finish
    blocks.append(meeting)
    blocks.sort(key=lambda block: _time(block["start_time"]))
    errors = validate_schedule(blocks, [block for block in current_blocks if block["title"] != "Planning"], current_time)
    if errors:
        raise ValueError("; ".join(errors))
    return blocks
