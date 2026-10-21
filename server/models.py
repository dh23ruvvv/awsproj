"""Pydantic request, response, data, and diff contracts from TASK-004."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Represent the documented ErrorDetail contract."""

    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Represent the documented ErrorEnvelope contract."""

    error: ErrorDetail


class SessionCreateRequest(BaseModel):
    """Represent the documented SessionCreateRequest contract."""

    seed: bool = True
    demo_timestamp: str | None = None


class SessionResponse(BaseModel):
    """Represent the documented SessionResponse contract."""

    session_id: str
    state_version: int
    provider: str
    seeded: bool


class SessionResetResponse(BaseModel):
    """Represent the documented SessionResetResponse contract."""

    reset: bool
    state_version: int


class AgentMessageRequest(BaseModel):
    """Represent the documented AgentMessageRequest contract."""

    message: str
    state_version: int


class ToolTraceItem(BaseModel):
    """Represent the documented ToolTraceItem contract."""

    tool: str
    args: dict
    result_summary: str
    duration_ms: int


class AgentMessageResponse(BaseModel):
    """Represent the documented AgentMessageResponse contract."""

    response: str
    plan_id: str | None = None
    has_proposal: bool = False
    state_version: int = 1
    provider_used: str = "deterministic"
    degraded: bool = False
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)


class CalendarBlockInput(BaseModel):
    """Represent the documented CalendarBlockInput contract."""

    title: str
    start_time: str
    end_time: str
    task_id: str | None = None
    immutable: bool = False


class DiffItem(BaseModel):
    """Represent the documented DiffItem contract."""

    block_id: str
    title: str


class DiffMovedItem(BaseModel):
    """Represent the documented DiffMovedItem contract."""

    block_id: str
    title: str
    old_start: str
    new_start: str


class DiffShortenedItem(BaseModel):
    """Represent the documented DiffShortenedItem contract."""

    block_id: str
    title: str
    old_duration_min: int
    new_duration_min: int


class DiffDroppedItem(BaseModel):
    """Represent the documented DiffDroppedItem contract."""

    block_id: str
    title: str
    reason: str


class DiffAddedItem(BaseModel):
    """Represent the documented DiffAddedItem contract."""

    title: str
    start_time: str
    end_time: str


class DiffSummary(BaseModel):
    """Represent the documented DiffSummary contract."""

    kept: list[DiffItem]
    moved: list[DiffMovedItem]
    shortened: list[DiffShortenedItem]
    dropped: list[DiffDroppedItem]
    added: list[DiffAddedItem]


class PlanDetailsResponse(BaseModel):
    """Represent the documented PlanDetailsResponse contract."""

    plan_id: str
    status: str
    proposed_blocks: list[dict]
    diff: DiffSummary | None
    explanation: str | None
    state_version_at_proposal: int
    provider_used: str
    degraded: bool


class PlanConfirmRequest(BaseModel):
    """Represent the documented PlanConfirmRequest contract."""

    state_version: int


class PlanConfirmResponse(BaseModel):
    """Represent the documented PlanConfirmResponse contract."""

    committed: bool
    state_version: int
    execution_log: list = Field(default_factory=list)
    already_executed: bool = False


class PlanCancelResponse(BaseModel):
    """Represent the documented PlanCancelResponse contract."""

    cancelled: bool
    state_version: int


class TaskModel(BaseModel):
    """Represent the documented TaskModel contract."""

    id: str
    session_id: str
    title: str
    duration_minutes: int
    deadline: str | None
    priority: str
    category: str
    status: str
    created_at: str


class CalendarBlockModel(BaseModel):
    """Represent the documented CalendarBlockModel contract."""

    id: str
    session_id: str
    title: str
    start_time: str
    end_time: str
    immutable: bool
    task_id: str | None
    status: str
    plan_id: str | None
    created_at: str


class MemoryEntryModel(BaseModel):
    """Represent the documented MemoryEntryModel contract."""

    id: str
    session_id: str
    key: str
    value: str
    created_at: str


class ExecutionLogEntryModel(BaseModel):
    """Represent the documented ExecutionLogEntryModel contract."""

    id: str
    session_id: str
    plan_id: str | None
    tool_name: str
    tool_args: str
    tool_result: str
    duration_ms: int
    created_at: str


class ScheduleResponse(BaseModel):
    """Represent the documented ScheduleResponse contract."""

    blocks: list[CalendarBlockModel]
    state_version: int


class TasksResponse(BaseModel):
    """Represent the documented TasksResponse contract."""

    tasks: list[TaskModel]
    state_version: int


class MemoryResponse(BaseModel):
    """Represent the documented MemoryResponse contract."""

    entries: list[MemoryEntryModel]
    state_version: int


class ExecutionLogResponse(BaseModel):
    """Represent the documented ExecutionLogResponse contract."""

    entries: list[ExecutionLogEntryModel]
