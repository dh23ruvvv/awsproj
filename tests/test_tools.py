"""Verify the registry contract and schema validation boundaries."""

import pytest
from jsonschema import ValidationError

from server.tools.registry import Tool, ToolRegistry, default_registry


def test_default_tools() -> None:
    """The singleton contains exactly the eight specified tools without handlers."""
    tools = default_registry.list_tools()
    assert len(tools) == 8
    assert {tool.name for tool in tools} == {
        "get_tasks", "get_calendar", "get_current_time", "get_schedule",
        "get_memory", "propose_schedule", "propose_replan", "commit_schedule",
    }
    assert all(tool.handler is None for tool in tools)


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
