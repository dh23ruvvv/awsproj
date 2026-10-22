"""Session-scoped agent turns and an in-memory sliding message limit."""

from collections import deque
from functools import lru_cache
import os
import sqlite3
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.database import get_connection
from server.clock import now
from server.config import settings
from server.models import AgentMessageResponse, ErrorDetail, ErrorEnvelope
from server.providers.base import AgentContext
from server.providers.deterministic import DeterministicProvider
from server.providers.fallback import FallbackProvider

router = APIRouter()
_message_times: dict[str, deque[float]] = {}
_rate_lock = Lock()


@lru_cache(maxsize=1)
def _live_provider(api_key: str) -> FallbackProvider:
    """Keep circuit state across requests; load the optional SDK only in live mode."""
    from server.providers.gemini import GeminiProvider

    return FallbackProvider(GeminiProvider(), DeterministicProvider())


class AgentMessageRequest(BaseModel):
    """Validate an utterance and its optional client state version."""

    message: str = Field(min_length=1, max_length=1000)
    state_version: int | None = None


def _error(status: int, code: str, message: str) -> JSONResponse:
    """Serialize the standard API error envelope."""
    envelope = ErrorEnvelope(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status, content=envelope.model_dump())


@router.post("/sessions/{sid}/agent/message", response_model=AgentMessageResponse)
async def agent_message(
    sid: str, request: AgentMessageRequest,
    provider: str | None = Query(default=None),
    provider_header: str | None = Header(default=None, alias="X-FlowPilot-Provider"),
) -> AgentMessageResponse | JSONResponse:
    """Run the selected provider against an existing session's real tools."""
    connection = get_connection()
    try:
        connection.execute("BEGIN")
        session_row = connection.execute("SELECT state_version, demo_timestamp FROM sessions WHERE id = ?", (sid,)).fetchone()
        if session_row is None:
            return _error(404, "SESSION_NOT_FOUND", "Session not found")
        if request.state_version is not None and request.state_version != session_row["state_version"]:
            return _error(409, "STALE_STATE", "Your workspace changed. Refresh before requesting a proposal.")
        if connection.execute("SELECT 1 FROM task_drafts WHERE session_id=? AND status='PROPOSED'", (sid,)).fetchone():
            return _error(409, "REVIEW_PENDING", "Confirm or cancel your task changes before starting another request.")
        with _rate_lock:
            current = monotonic()
            if len(_message_times) > 100:
                expired = [k for k, q in _message_times.items() if not q or current - q[-1] >= 120]
                for k in expired:
                    del _message_times[k]
            timestamps = _message_times.setdefault(sid, deque())
            while timestamps and current - timestamps[0] >= 60:
                timestamps.popleft()
            if len(timestamps) >= 10:
                return _error(429, "RATE_LIMIT_EXCEEDED",
                              "Rate limit exceeded. Maximum 10 messages per minute per session.")
            timestamps.append(current)

        selected = provider or provider_header or settings.flowpilot_default_provider
        if selected not in {"gemini", "deterministic"}:
            return _error(400, "INVALID_PROVIDER", "Provider must be gemini or deterministic")
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        active_provider = _live_provider(api_key) if selected == "gemini" and api_key else DeterministicProvider()
        history = [dict(row) for row in connection.execute('SELECT role,content FROM agent_messages WHERE session_id=? ORDER BY id DESC LIMIT 12', (sid,))][::-1]
        context = AgentContext(session_id=sid, db_conn=connection, current_time=now(session_row['demo_timestamp']), conversation_history=history)
        try:
            result = await active_provider.run_agent_turn(request.message, context)
        except (ValueError, TypeError) as exc:
            connection.rollback()
            return _error(422, "CANNOT_SCHEDULE", str(exc))
        except sqlite3.OperationalError:
            connection.rollback()
            return _error(409, "STATE_CHANGED", "Workspace changed while planning. Refresh and try again.")
        if selected == "gemini" and not api_key:
            result.degraded = True
            result.provider_used = "gemini-fallback"
        if result.plan_id:
            connection.execute("UPDATE plans SET provider_used=?,degraded=? WHERE id=? AND session_id=?",
                               (result.provider_used, int(result.degraded), result.plan_id, sid))
        state_version = connection.execute(
            "SELECT state_version FROM sessions WHERE id = ?", (sid,)
        ).fetchone()["state_version"]
        connection.execute('INSERT INTO agent_messages (session_id,role,content) VALUES (?,?,?)', (sid, 'user', request.message))
        connection.execute('INSERT INTO agent_messages (session_id,role,content) VALUES (?,?,?)', (sid, 'assistant', result.response[:4000]))
        connection.execute('DELETE FROM agent_messages WHERE session_id=? AND id NOT IN (SELECT id FROM agent_messages WHERE session_id=? ORDER BY id DESC LIMIT 12)', (sid, sid))
        connection.commit()
        return AgentMessageResponse(
            response=result.response, plan_id=result.plan_id, task_draft_id=result.task_draft_id,
            has_proposal=result.has_proposal, state_version=state_version,
            provider_used=result.provider_used, degraded=result.degraded,
            tool_trace=result.tool_trace,
        )
    finally:
        connection.close()
