"""Register tool metadata and validate arguments using the specified schemas."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import jsonschema
from server.tools.commit_tools import commit_schedule
from server.tools.propose_tools import propose_schedule, propose_replan

from server.tools.read_tools import (
    get_calendar, get_current_time, get_memory, get_schedule, get_tasks,
)


@dataclass
class Tool:
    """Describe a tool without requiring an executable handler."""

    name: str
    tier: Literal["READ", "PROPOSE", "COMMIT"]
    description: str
    input_schema: dict
    handler: Callable | None = None


class ToolRegistry:
    """Store named tools and validate their input arguments."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return the named tool, raising KeyError when it is unknown."""
        return self._tools[name]

    def list_tools(self, tier: str | None = None) -> list[Tool]:
        """Return all tools, optionally filtered by tier."""
        return [tool for tool in self._tools.values() if tier is None or tool.tier == tier]

    def validate_args(self, name: str, args: dict) -> None:
        """Raise ValidationError when arguments violate the tool schema."""
        jsonschema.validate(instance=args, schema=self.get(name).input_schema)


def _object_schema(properties: dict, required: list[str] | None = None) -> dict:
    """Build a tool input object that rejects unspecified properties."""
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required is not None:
        schema["required"] = required
    return schema


def _proposal_schema(blocks_key: str) -> dict:
    """Build the specified schedule or replan input schema."""
    return _object_schema(
        {
            blocks_key: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string", "maxLength": 200},
                        "start_time": {"type": "string", "format": "date-time"},
                        "end_time": {"type": "string", "format": "date-time"},
                        "task_id": {"type": "string"},
                        "immutable": {"type": "boolean", "default": False},
                    },
                    "required": ["title", "start_time", "end_time"],
                },
            },
            "explanation": {"type": "string", "maxLength": 500},
        },
        [blocks_key, "explanation"],
    )


default_registry = ToolRegistry()
for _tool in (
    Tool("get_tasks", "READ", "List tasks for current session", _object_schema({
        "status": {"type": "string", "enum": ["pending", "scheduled", "completed", "cancelled"]},
    }), get_tasks),
    Tool("get_calendar", "READ", "Get calendar blocks for session", _object_schema({
        "date": {"type": "string", "format": "date"},
    }), get_calendar),
    Tool("get_current_time", "READ", "Get current time (injectable)", _object_schema({}), get_current_time),
    Tool("get_schedule", "READ", "Get committed schedule", _object_schema({}), get_schedule),
    Tool("get_memory", "READ", "Retrieve stored memory entries", _object_schema({}), get_memory),
    Tool("propose_schedule", "PROPOSE", "Propose a new day schedule", _proposal_schema("blocks"), propose_schedule),
    Tool("propose_replan", "PROPOSE", "Propose schedule changes after interruption", _proposal_schema("new_blocks"), propose_replan),
    Tool("commit_schedule", "COMMIT", "Commit approved plan to schedule", _object_schema(
        {"plan_id": {"type": "string"}}, ["plan_id"],
    ), commit_schedule),
):
    default_registry.register(_tool)
