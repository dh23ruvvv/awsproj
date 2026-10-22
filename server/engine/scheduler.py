"""Pure, deterministic interval fitting with full task durations and safe failures."""

from copy import deepcopy
from datetime import timedelta

from .validator import _time, validate_schedule


def _checked_time(value):
    parsed = _time(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamps must include a timezone offset")
    return parsed


def _check_blocks(blocks, current_time):
    for block in blocks:
        _checked_time(block["start_time"])
        _checked_time(block["end_time"])
    errors = validate_schedule(blocks, existing_blocks=blocks, current_time=current_time)
    if errors:
        raise ValueError("; ".join(errors))


def _fit(blocks, earliest, duration, latest, title):
    """Find the first whole free interval; never shorten a task to fit a gap."""
    start = earliest
    for block in sorted(blocks, key=lambda item: _time(item["start_time"])):
        left, right = _time(block["start_time"]), _time(block["end_time"])
        if right <= start:
            continue
        if start + duration <= left:
            break
        start = right
    if start + duration > latest:
        raise ValueError(
            f"Cannot schedule {title} for its full {duration.total_seconds() / 60:g} minutes "
            "within the working day/deadline. Shorten the task, change its deadline, "
            "or free up calendar time and try again."
        )
    return start, start + duration


def compute_day_schedule(tasks, calendar_blocks, current_time):
    """Fit full-duration tasks around existing commitments in the 09:00–17:00 day.

    Existing reservations and their identities are retained. Tasks already in the
    calendar are not duplicated. Impossible requests fail without mutating inputs.
    """
    now = _checked_time(current_time)
    _check_blocks(calendar_blocks, current_time)
    origin = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = origin + timedelta(hours=8)
    blocks = deepcopy(calendar_blocks)
    assigned = {block.get("task_id") for block in blocks}
    pending = [task for task in tasks if task["id"] not in assigned and
               task.get("status", "pending").lower() not in ("completed", "cancelled")]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    pending.sort(key=lambda task: (rank.get(task.get("priority", "LOW").upper(), 2),
                                   _checked_time(task["deadline"]) if task.get("deadline") else day_end))
    for task in pending:
        minutes = task["duration_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
            raise ValueError(f"Invalid positive duration for {task['title']}")
        latest = min(day_end, _checked_time(task["deadline"])) if task.get("deadline") else day_end
        start, end = _fit(blocks, max(origin, now), timedelta(minutes=minutes), latest, task["title"])
        blocks.append({"title": task["title"], "task_id": task["id"],
                       "start_time": start.isoformat(), "end_time": end.isoformat(),
                       "immutable": False})
    blocks.sort(key=lambda block: _time(block["start_time"]))
    _check_blocks(blocks, current_time)
    return blocks


def compute_replan(current_blocks, interruption, current_time):
    """Fit interrupted work around protected intervals, retaining IDs and durations."""
    now = _checked_time(current_time)
    _check_blocks(current_blocks, current_time)
    meeting = deepcopy(interruption)
    _check_blocks([meeting], current_time)
    start, end = _time(meeting["start_time"]), _time(meeting["end_time"])
    day_end = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if start < now or end <= start:
        raise ValueError("Interruption must be a future positive interval")
    # An accepted interruption becomes a fixed commitment in the proposal.
    meeting["immutable"] = True
    blocks, movable = [meeting], []
    for original in current_blocks:
        block = deepcopy(original)
        left, right = _time(block["start_time"]), _time(block["end_time"])
        protected = (block.get("immutable") or
                     str(block.get("status", "")).lower() == "completed" or left < now)
        if protected and start < right and left < end:
            raise ValueError("Interruption overlaps protected or in-progress block")
        if protected or right <= start:
            blocks.append(block)
        else:
            movable.append(block)
    for block in sorted(movable, key=lambda item: _time(item["start_time"])):
        left, right = _time(block["start_time"]), _time(block["end_time"])
        latest = min(day_end, _checked_time(block["deadline"])) if block.get("deadline") else day_end
        new_start, new_end = _fit(blocks, max(left, now), right - left, latest, block["title"])
        block.update(start_time=new_start.isoformat(), end_time=new_end.isoformat())
        blocks.append(block)
    blocks.sort(key=lambda block: _time(block["start_time"]))
    errors = validate_schedule(blocks, current_blocks, current_time)
    if errors:
        raise ValueError("; ".join(errors))
    return blocks
