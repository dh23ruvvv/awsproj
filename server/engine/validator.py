"""Validate proposals without changing caller-owned calendar data."""

from datetime import datetime


def _time(value):
    """Parse a full ISO timestamp, rejecting date-only values."""
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("expected ISO8601 date-time")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _identity(block):
    """Prefer persistent identity, with a stable fallback for input blocks."""
    return block.get("block_id", block.get("id", (block.get("task_id"), block.get("title"))))


def validate_schedule(blocks, existing_blocks=None, current_time=None):
    """Return errors for malformed intervals, overlaps, or changed protected blocks."""
    errors = []
    intervals = []
    try:
        now = _time(current_time) if current_time is not None else None
    except (ValueError, TypeError):
        errors.append("Invalid current_time ISO8601 timestamp")
        now = None
    for index, block in enumerate(blocks):
        try:
            start, end = _time(block.get("start_time")), _time(block.get("end_time"))
            if start >= end:
                errors.append(f"Block {index}: start_time must precede end_time")
            else:
                intervals.append((start, end, index))
            if now is not None and (start.date() != now.date() or end.date() != now.date()):
                errors.append(f"Block {index}: outside current day bounds")
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
        if not (old.get("immutable") or str(old.get("status", "")).lower() == "completed"):
            continue
        matches = [
            new for new in blocks
            if _identity(new) == _identity(old)
            or (new.get("title") and new.get("title") == old.get("title"))
            or (new.get("task_id") and new.get("task_id") == old.get("task_id"))
        ]
        if not any(new.get("start_time") == old.get("start_time") and
                   new.get("end_time") == old.get("end_time") and
                   (not old.get("task_id") or not new.get("task_id") or new.get("task_id") == old.get("task_id")) and
                   new.get("title") == old.get("title") for new in matches):
            errors.append(f"Protected completed/immutable block modified or removed: {old.get('title')}")
    return errors
