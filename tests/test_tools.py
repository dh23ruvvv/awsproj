"""Verify the registry contract and schema validation boundaries."""

from datetime import datetime, timezone

import pytest
from jsonschema import ValidationError

from server.tools.registry import Tool, ToolRegistry, default_registry
from server.database import SCHEMA, get_connection, seed_session


def test_default_tools() -> None:
    """The singleton contains eight tools with handlers only for READ tools."""
    tools = default_registry.list_tools()
    assert len(tools) == 8
    assert {tool.name for tool in tools} == {
        "get_tasks", "get_calendar", "get_current_time", "get_schedule",
        "get_memory", "propose_schedule", "propose_replan", "commit_schedule",
    }
    assert all(callable(tool.handler) for tool in tools if tool.tier == "READ")
    assert all(tool.handler is None for tool in tools if tool.tier != "READ")


@pytest.mark.parametrize("tier,count", [("READ", 5), ("PROPOSE", 2), ("COMMIT", 1)])
def test_tier_filter(tier: str, count: int) -> None:
    """Tier filters return only tools from the requested tier."""
    tools = default_registry.list_tools(tier)
    assert len(tools) == count
    assert all(tool.tier == tier for tool in tools)


@pytest.mark.parametrize("name,args", [
    ("get_tasks", {}),
    *[("get_tasks", {"status": status}) for status in ("pending", "scheduled", "completed", "cancelled")],
    ("get_calendar", {}), ("get_calendar", {"date": "2026-10-21"}),
    ("get_current_time", {}), ("get_schedule", {}), ("get_memory", {}),
    ("propose_schedule", {"blocks": [], "explanation": ""}),
    ("propose_replan", {"new_blocks": [], "explanation": ""}),
    ("commit_schedule", {"plan_id": "plan-1"}),
])
def test_valid_args(name: str, args: dict) -> None:
    """Accept valid inputs, including optional filters and empty proposals."""
    assert default_registry.validate_args(name, args) is None


@pytest.mark.parametrize("name,args", [
    ("get_tasks", {"status": "unknown"}), ("get_tasks", {"status": 1}),
    ("get_calendar", {"date": 1}),
    *[(name, {"extra": True}) for name in (
        "get_tasks", "get_calendar", "get_current_time", "get_schedule", "get_memory",
    )],
    ("commit_schedule", {}), ("commit_schedule", {"plan_id": 1}),
    ("commit_schedule", {"plan_id": "p", "extra": True}),
    ("get_tasks", []),
])
def test_invalid_args(name: str, args: dict) -> None:
    """Reject invalid types, enum values, missing fields and extra arguments."""
    with pytest.raises(ValidationError):
        default_registry.validate_args(name, args)


@pytest.mark.parametrize("name,key", [("propose_schedule", "blocks"), ("propose_replan", "new_blocks")])
def test_proposal_boundaries(name: str, key: str) -> None:
    """Check nested required fields, types and length limits for both proposals."""
    block = {
        "title": "x" * 200, "start_time": "2026-10-21T09:00:00Z",
        "end_time": "2026-10-21T10:00:00Z", "task_id": "task-1", "immutable": False,
    }
    args = {key: [block], "explanation": "x" * 500}
    default_registry.validate_args(name, args)
    for invalid in (
        {key: []}, {"explanation": "reason"},
        {**args, "extra": True}, {**args, key: "invalid"},
        {**args, "explanation": "x" * 501},
        *[{**args, key: [{k: v for k, v in block.items() if k != field}]} for field in ("title", "start_time", "end_time")],
        *[{**args, key: [{**block, field: value}]} for field, value in (
            ("title", "x" * 201), ("start_time", 1), ("end_time", None),
            ("task_id", 1), ("immutable", "false"),
        )],
    ):
        with pytest.raises(ValidationError):
            default_registry.validate_args(name, invalid)
    assert args[key][0] == block


def test_registration_and_unknown_tool() -> None:
    """Registries are independent and unknown names raise KeyError."""
    registry = ToolRegistry()
    tool = Tool("example", "READ", "Example tool", {"type": "object"})
    registry.register(tool)
    assert registry.get("example") is tool
    assert registry.list_tools() == [tool]
    for operation in (lambda: registry.get("missing"), lambda: registry.validate_args("missing", {})):
        with pytest.raises(KeyError):
            operation()


@pytest.fixture
def seeded_db():
    """Create two isolated seeded sessions in a real in-memory database."""
    connection = get_connection(":memory:")
    try:
        connection.executescript(SCHEMA)
        for sid, timestamp in (("session", "2026-10-21T09:00:00+05:30"), ("other", None)):
            connection.execute(
                "INSERT INTO sessions (id, created_at, demo_timestamp) VALUES (?, ?, ?)",
                (sid, "2026-10-21T00:00:00Z", timestamp),
            )
            seed_session(connection, sid)
        connection.commit()
        yield connection
    finally:
        connection.close()


def call_read(connection, name, args=None, sid="session"):
    """Validate and invoke the registered handler without allowing database writes."""
    arguments = {} if args is None else args
    default_registry.validate_args(name, arguments)
    connection.execute("PRAGMA query_only = ON")
    try:
        return default_registry.get(name).handler(sid, arguments, connection)
    finally:
        connection.execute("PRAGMA query_only = OFF")


def test_get_tasks(seeded_db):
    """Read five seeded tasks and filter all statuses within one session."""
    tasks = call_read(seeded_db, "get_tasks")["tasks"]
    assert len(tasks) == 5
    assert all(task["session_id"] == "session" for task in tasks)
    for status in ("pending", "scheduled", "completed", "cancelled"):
        assert call_read(seeded_db, "get_tasks", {"status": status}) == {
            "tasks": [task for task in tasks if task["status"] == status],
        }
    assert call_read(seeded_db, "get_tasks", sid="session' OR 1=1 --") == {"tasks": []}


def test_get_calendar(seeded_db):
    """Read two seeded blocks and apply the date filter without leaking sessions."""
    blocks = call_read(seeded_db, "get_calendar")["blocks"]
    assert len(blocks) == 2
    assert all(block["session_id"] == "session" for block in blocks)
    date = blocks[0]["start_time"][:10]
    assert call_read(seeded_db, "get_calendar", {"date": date}) == {
        "blocks": [block for block in blocks if block["start_time"].startswith(date)],
    }
    assert call_read(seeded_db, "get_calendar", {"date": "1900-01-01"}) == {"blocks": []}


def test_get_current_time(seeded_db):
    """Use the exact demo override, or a current aware clock when it is absent."""
    result = call_read(seeded_db, "get_current_time")
    assert result == {"current_time": "2026-10-21T09:00:00+05:30", "timezone": "Asia/Kolkata"}
    assert datetime.fromisoformat(result["current_time"]).utcoffset() is not None
    before = datetime.now(timezone.utc)
    live = call_read(seeded_db, "get_current_time", sid="other")
    after = datetime.now(timezone.utc)
    assert before <= datetime.fromisoformat(live["current_time"]) <= after
    assert live["timezone"] == "Asia/Kolkata"


def test_get_schedule(seeded_db):
    """Return the committed blocks in time order and read the persisted version."""
    result = call_read(seeded_db, "get_schedule")
    assert result["state_version"] == 1
    assert len(result["blocks"]) == 2
    assert all(block["session_id"] == "session" for block in result["blocks"])
    starts = [block["start_time"] for block in result["blocks"]]
    assert starts == sorted(starts)
    seeded_db.execute("UPDATE sessions SET state_version = ? WHERE id = ?", (7, "session"))
    assert call_read(seeded_db, "get_schedule")["state_version"] == 7
    assert call_read(seeded_db, "get_schedule", sid="other")["state_version"] == 1


def test_get_memory(seeded_db):
    """Return empty seed memory and only entries owned by the requested session."""
    assert call_read(seeded_db, "get_memory") == {"entries": []}
    for sid in ("session", "other"):
        seeded_db.execute(
            "INSERT INTO memory (id, session_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
            (sid, sid, "preference", sid, "2026-10-21T00:00:00Z"),
        )
    entries = call_read(seeded_db, "get_memory")["entries"]
    assert len(entries) == 1
    assert entries[0]["session_id"] == "session"
    assert entries[0]["value"] == "session"
