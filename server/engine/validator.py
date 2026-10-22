"""Validate proposals without changing caller-owned calendar data."""

from datetime import datetime
from copy import deepcopy


def _time(value):
    """Parse a full ISO timestamp, rejecting date-only values."""
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("expected ISO8601 date-time")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _identity(block):
    """Prefer persistent identity, with a stable fallback for input blocks."""
    return block.get("block_id", block.get("id", (block.get("task_id"), block.get("title"))))


def inherit_block_metadata(blocks, existing_blocks):
    """Resolve omitted metadata to a unique existing block without changing caller input."""
    result = deepcopy(blocks)
    available = list(existing_blocks)
    for block in result:
        matches = [old for old in available if old.get("id") == block.get("id")] if block.get("id") else [
            old for old in available if old.get("title") == block.get("title") and
            ("task_id" not in block or old.get("task_id") == block.get("task_id"))]
        if len(matches) > 1:
            matches = [old for old in matches if old.get("start_time") == block.get("start_time")
                       and old.get("end_time") == block.get("end_time")]
        if len(matches) != 1:
            continue
        old = matches[0]
        for key in ("id", "task_id", "status", "immutable"):
            if old.get(key) is not None:
                block.setdefault(key, old[key])
        available.remove(old)
    return result


def validate_schedule(blocks, existing_blocks=None, current_time=None):
    """Return errors for malformed intervals, overlaps, or changed protected blocks."""
    errors = []
    intervals = []
    identities = [block.get("id") for block in blocks if block.get("id")]
    if len(identities) != len(set(identities)):
        errors.append("Duplicate block identity")
    try:
        now = _time(current_time) if current_time is not None else None
    except (ValueError, TypeError):
        errors.append("Invalid current_time ISO8601 timestamp")
        now = None
    for index, block in enumerate(blocks):
        try:
            start, end = _time(block.get("start_time")), _time(block.get("end_time"))
            if start.tzinfo is None or end.tzinfo is None:
                errors.append(f"Block {index}: timestamps must include a timezone offset")
            if start >= end:
                errors.append(f"Block {index}: start_time must precede end_time")
            else:
                intervals.append((start, end, index))
            if now is not None and (start.date() != now.date() or end.date() != now.date()):
                errors.append(f"Block {index}: outside current day bounds")
            if now is not None and start < now and not any(
                    old.get("start_time") == block.get("start_time") and
                    old.get("end_time") == block.get("end_time") and
                    old.get("title") == block.get("title") for old in existing_blocks or []):
                errors.append(f"Block {index}: cannot add or move work into the past")
        except (ValueError, TypeError):
            errors.append(f"Block {index}: invalid ISO8601 timestamps or inconsistent timezone")
    for position, (start, end, index) in enumerate(intervals):
        for other_start, other_end, other_index in intervals[position + 1:]:
            try:
                if start < other_end and other_start < end:
                    errors.append(f"Blocks {index} and {other_index} overlap")
            except TypeError:
                errors.append("Inconsistent timezone awareness between blocks")
    for old in existing_blocks or []:
        if not (old.get("immutable") or str(old.get("status", "")).lower() == "completed"
                or (now is not None and _time(old["start_time"]) < now)):
            continue
        matches = [
            new for new in blocks
            if (_identity(new) == _identity(old)
            or (new.get("title") and new.get("title") == old.get("title"))
            or (new.get("task_id") and new.get("task_id") == old.get("task_id")))
            and (not old.get("id") or not new.get("id") or new.get("id") == old.get("id"))
        ]
        if not any(new.get("start_time") == old.get("start_time") and
                   new.get("end_time") == old.get("end_time") and
                   ("task_id" not in new or new.get("task_id") == old.get("task_id")) and
                   (old.get("status") != "completed" or new.get("status", "completed") == "completed") and
                   new.get("title") == old.get("title") for new in matches):
            errors.append(f"Protected completed/immutable block modified or removed: {old.get('title')}")
        elif old.get("immutable") and not any(new.get("immutable") for new in matches):
            errors.append(f"Protected block cannot be unlocked: {old.get('title')}")
    return errors
