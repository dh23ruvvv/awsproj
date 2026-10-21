"""Injectable, timezone-aware clock for demo and real-time operation."""

from datetime import datetime, timezone


def now(demo_timestamp: str | None = None) -> str:
    """Return the supplied demo timestamp or the current UTC ISO8601 time.

    Reject demo timestamps without a timezone to keep clock values unambiguous.
    """
    if demo_timestamp is not None:
        instant = datetime.fromisoformat(demo_timestamp.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("demo_timestamp must include a timezone")
        return instant.isoformat()
    return datetime.now(timezone.utc).isoformat()
