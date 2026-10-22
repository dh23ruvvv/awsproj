"""Shared context, result, and protocol for scheduling providers."""

from dataclasses import dataclass, field
from sqlite3 import Connection
from typing import Protocol, TypedDict


class ToolTraceItem(TypedDict):
    """Serializable record of one executed tool."""

    tool: str
    args: dict
    result_summary: str
    duration_ms: int


@dataclass
class AgentContext:
    """Session data available to a provider for one turn."""

    session_id: str
    db_conn: Connection
    current_time: str | None = None
    conversation_history: list[dict] = field(default_factory=list)


@dataclass
class AgentTurnResult:
    """User response and executed tool metadata for one turn."""

    response: str
    task_draft_id: str | None = None
    plan_id: str | None = None
    has_proposal: bool = False
    state_version: int = 1
    provider_used: str = "deterministic"
    degraded: bool = False
    tool_trace: list[dict] = field(default_factory=list)


class Provider(Protocol):
    """Asynchronous provider contract shared by all implementations."""

    async def run_agent_turn(self, message: str, context: AgentContext) -> AgentTurnResult:
        """Execute a scheduling turn for the supplied session."""
        ...
