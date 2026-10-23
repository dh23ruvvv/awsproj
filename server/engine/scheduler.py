"""Pure, deterministic interval fitting with full task durations and safe failures."""

from copy import deepcopy
from datetime import timedelta
import re

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


def _chunks(blocks, earliest, duration, latest, title):
    """Use free intervals with at least 30 minutes; leave no tiny final chunk."""
    minimum = timedelta(minutes=30)
    remaining, cursor, chunks = duration, earliest, []
    intervals = sorted(blocks, key=lambda item: _time(item['start_time']))
    for block in intervals + [{'start_time': latest.isoformat(), 'end_time': latest.isoformat()}]:
        left, right = _time(block['start_time']), _time(block['end_time'])
        end = min(left, latest)
        capacity = end - cursor
        if capacity >= minimum:
            take = min(capacity, remaining)
            if timedelta(0) < remaining - take < minimum:
                take = remaining - minimum
            if take >= minimum:
                chunks.append((cursor, cursor + take))
                remaining -= take
                if remaining == timedelta(0):
                    return chunks
        cursor = max(cursor, right)
        if cursor >= latest:
            break
    raise ValueError(f"Cannot schedule {title} for its full {duration.total_seconds() / 60:g} minutes within the working day/deadline.")


def _place(blocks, earliest, duration, preferred_end, latest, title, preferred_start=None):
    """Try whole slots, then chunks, within primary bounds before evening overflow."""
    for bound in dict.fromkeys((min(preferred_end, latest), latest)):
        starts = [earliest]
        if preferred_start is not None and preferred_start > earliest:
            starts.insert(0, preferred_start)
        for start in starts:
            try:
                return [_fit(blocks, start, duration, bound, title)]
            except ValueError:
                if duration > timedelta(minutes=60):
                    try:
                        return _chunks(blocks, start, duration, bound, title)
                    except ValueError:
                        pass
    raise ValueError(f"Cannot schedule {title} for its full {duration.total_seconds() / 60:g} minutes within the working day/deadline (maximum 21:00).")


def _preference_hour(task, preferences):
    """Recognize documented soft preferences; unrecognized text remains visible memory."""
    category = task.get('category', 'work')
    for entry in reversed(preferences or []):
        text = str(entry.get('value', '')).lower()
        applies = ((category == 'personal' and re.search(r'\b(personal|errands)\b', text)) or
                   (category == 'work' and re.search(r'\b(work|focus)\b', text)))
        if not applies:
            continue
        after = re.search(r'\bafter\s+(1[0-2]|[1-9])(?::([0-5]\d))?\s*(am|pm)\b', text)
        if after:
            hour = int(after[1]) % 12 + (12 if after[3] == 'pm' else 0)
            return hour + int(after[2] or 0) / 60
        if 'morning' in text:
            return 9
        if 'afternoon' in text:
            return 13
    return None


def compute_day_schedule(tasks, calendar_blocks, current_time, preferences=None):
    """Prefer 09:00–17:00, splitting long tasks and overflowing no later than 21:00.

    Existing reservations and their identities are retained. Tasks already in the
    calendar are not duplicated. Impossible requests fail without mutating inputs.
    """
    now = _checked_time(current_time)
    _check_blocks(calendar_blocks, current_time)
    origin = now.replace(hour=9, minute=0, second=0, microsecond=0)
    preferred_end = origin + timedelta(hours=8)
    day_end = origin + timedelta(hours=12)
    blocks = deepcopy(calendar_blocks)
    assigned = {block.get("task_id") for block in blocks}
    pending = [task for task in tasks if task["id"] not in assigned and
               task.get("status", "pending").lower() not in ("completed", "cancelled")]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    pending.sort(key=lambda task: (rank.get(task.get("priority", "LOW").upper(), 2),
                                   _checked_time(task["deadline"]) if task.get("deadline") else day_end,
                                   _preference_hour(task, preferences) or 9))
    for task in pending:
        minutes = task["duration_minutes"]
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
            raise ValueError(f"Invalid positive duration for {task['title']}")
        latest = min(day_end, _checked_time(task["deadline"])) if task.get("deadline") else day_end
        hour = _preference_hour(task, preferences)
        preference_start = origin + timedelta(hours=hour - 9) if hour is not None else None
        for start, end in _place(blocks, max(origin, now), timedelta(minutes=minutes), preferred_end, latest, task["title"], preference_start):
            blocks.append({"title": task["title"], "task_id": task["id"],
                           "start_time": start.isoformat(), "end_time": end.isoformat(),
                           "immutable": False})
    blocks.sort(key=lambda block: _time(block["start_time"]))
    _check_blocks(blocks, current_time)
    return blocks


def compute_replan(current_blocks, interruption, current_time, tasks=None):
    """Fit interrupted work around protected intervals, retaining IDs and durations."""
    now = _checked_time(current_time)
    _check_blocks(current_blocks, current_time)
    meeting = deepcopy(interruption)
    _check_blocks([meeting], current_time)
    start, end = _time(meeting["start_time"]), _time(meeting["end_time"])
    preferred_end = now.replace(hour=17, minute=0, second=0, microsecond=0)
    day_end = preferred_end + timedelta(hours=4)
    if start < now or end <= start:
        raise ValueError("Interruption must be a future positive interval")
    # An accepted interruption becomes a fixed commitment in the proposal.
    meeting["immutable"] = True
    blocks, movable = [meeting], []
    deadlines = {task['id']: task.get('deadline') for task in tasks or []}
    for original in current_blocks:
        block = deepcopy(original)
        if deadlines.get(block.get('task_id')):
            block['deadline'] = deadlines[block['task_id']]
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
        for index, (new_start, new_end) in enumerate(_place(blocks, max(left, now), right - left, preferred_end, latest, block["title"])):
            chunk = dict(block, start_time=new_start.isoformat(), end_time=new_end.isoformat())
            if index:
                chunk.pop('id', None)
                chunk.pop('block_id', None)
            blocks.append(chunk)
    blocks.sort(key=lambda block: _time(block["start_time"]))
    errors = validate_schedule(blocks, current_blocks, current_time)
    if errors:
        raise ValueError("; ".join(errors))
    return blocks
