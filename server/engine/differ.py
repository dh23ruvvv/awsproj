"""Compute wire-format schedule differences by persistent block identity."""

from .validator import _identity, _time


def compute_diff(old_blocks, new_blocks):
    """Classify changes; moving and shortening may both apply to one block."""
    result = {key: [] for key in ("kept", "moved", "shortened", "dropped", "added")}
    remaining = list(new_blocks)
    for old in old_blocks:
        match = next((new for new in remaining if _identity(new) == _identity(old)), None)
        if match is None:
            match = next((new for new in remaining if (new.get("title") and new.get("title") == old.get("title")) or (new.get("task_id") and new.get("task_id") == old.get("task_id"))), None)
        base = {"block_id": str(old.get("block_id", old.get("id", _identity(old)))), "title": old["title"]}
        if match is None:
            result["dropped"].append({**base, "reason": "Not present in proposed schedule"})
            continue
        remaining.remove(match)
        if old["start_time"] == match["start_time"] and old["end_time"] == match["end_time"]:
            result["kept"].append(base)
        if old["start_time"] != match["start_time"]:
            result["moved"].append({**base, "old_start": old["start_time"], "new_start": match["start_time"]})
        old_duration = int((_time(old["end_time"]) - _time(old["start_time"])).total_seconds() / 60)
        new_duration = int((_time(match["end_time"]) - _time(match["start_time"])).total_seconds() / 60)
        if new_duration < old_duration:
            result["shortened"].append({**base, "old_duration_min": old_duration, "new_duration_min": new_duration})
    result["added"] = [{key: block[key] for key in ("title", "start_time", "end_time")} for block in remaining]
    return result
