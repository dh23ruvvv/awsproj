"""Session-scoped agent turns and an in-memory sliding message limit."""

from collections import deque
from functools import lru_cache
import os
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.database import get_connection
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
        if connection.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone() is None:
            return _error(404, "SESSION_NOT_FOUND", "Session not found")
        with _rate_lock:
            current = monotonic()
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
        context = AgentContext(session_id=sid, db_conn=connection)
        result = await active_provider.run_agent_turn(request.message, context)
        state_version = connection.execute(
            "SELECT state_version FROM sessions WHERE id = ?", (sid,)
        ).fetchone()["state_version"]
        return AgentMessageResponse(
            response=result.response, plan_id=result.plan_id,
            has_proposal=result.has_proposal, state_version=state_version,
            provider_used=result.provider_used, degraded=result.degraded,
            tool_trace=result.tool_trace,
        )
    finally:
        connection.close()
