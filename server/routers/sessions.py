"""Create and reset isolated SQLite sessions."""

from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.config import settings
from server.database import get_connection, seed_session
from server.models import (
    ErrorDetail, ErrorEnvelope, SessionCreateRequest, SessionResetResponse,
    SessionResponse,
)

router = APIRouter()
_last_reset: dict[str, float] = {}
_reset_lock = Lock()


def _error(status: int, code: str, message: str) -> JSONResponse:
    """Return the API error envelope without FastAPI's detail wrapper."""
    envelope = ErrorEnvelope(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=envelope.model_dump())


@router.post("/sessions", status_code=201, response_model=SessionResponse)
def create_session(request: SessionCreateRequest) -> SessionResponse:
    """Create a server-generated session and optionally seed its demo data."""
    sid = str(uuid4())
    provider = settings.flowpilot_default_provider
    demo_timestamp = request.demo_timestamp
    if "demo_timestamp" not in request.model_fields_set:
        demo_timestamp = settings.flowpilot_demo_timestamp
    connection = get_connection()
    try:
        with connection:
            connection.execute(
                "INSERT INTO sessions (id, created_at, state_version, demo_timestamp, provider) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, datetime.now(timezone.utc).isoformat(), 1, demo_timestamp, provider),
            )
            if request.seed:
                seed_session(connection, sid)
    finally:
        connection.close()
    return SessionResponse(session_id=sid, state_version=1, provider=provider, seeded=request.seed)


@router.delete("/sessions/{sid}", response_model=SessionResetResponse)
def reset_session(sid: str) -> SessionResetResponse | JSONResponse:
    """Atomically clear and re-seed a session, allowing one reset per five seconds."""
    with _reset_lock:
        connection = get_connection()
        try:
            with connection:
                if connection.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone() is None:
                    return _error(404, "NOT_FOUND", "Session not found.")
                current = monotonic()
                previous = _last_reset.get(sid)
                if previous is not None and current - previous < 5:
                    return _error(429, "RATE_LIMITED", "Reset rate limit exceeded. Please wait 5 seconds.")
                connection.execute("DELETE FROM execution_log WHERE session_id = ?", (sid,))
                connection.execute("DELETE FROM calendar_blocks WHERE session_id = ?", (sid,))
                connection.execute("DELETE FROM plans WHERE session_id = ?", (sid,))
                connection.execute("DELETE FROM tasks WHERE session_id = ?", (sid,))
                connection.execute("DELETE FROM memory WHERE session_id = ?", (sid,))
                connection.execute("UPDATE sessions SET state_version = ? WHERE id = ?", (1, sid))
                seed_session(connection, sid)
            _last_reset[sid] = monotonic()
        finally:
            connection.close()
    return SessionResetResponse(reset=True, state_version=1)
