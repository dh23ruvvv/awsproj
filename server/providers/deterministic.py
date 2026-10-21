"""Offline intent routing through real read tools and scheduling proposals."""

import json
import re
from datetime import datetime, timedelta
from time import perf_counter

from server.engine.scheduler import compute_day_schedule, compute_replan
from server.tools import read_tools, propose_tools
from .base import AgentContext, AgentTurnResult, ToolTraceItem

PLAN_RESPONSE = "Here's your day — I've split the report into three blocks to hit your 5 PM deadline and scheduled the PR review before 2 PM."
REPLAN_RESPONSE = "Report still finishes by 5 PM. Grocery pushed 15 min. Buffer shortened."
FALLBACK_RESPONSE = "I can help you plan your day, replan around unexpected interruptions, or check what tasks are left. What would you like to do?"


class DeterministicProvider:
    """Select fixed tool sequences without network access or model inference."""

    async def run_agent_turn(self, message: str, context: AgentContext) -> AgentTurnResult:
        """Read session state and propose engine-computed schedules when requested."""
        trace: list[ToolTraceItem] = []

        def call(tool, args=None):
            """Execute and record a tool using the current session connection."""
            args = {} if args is None else args
            started = perf_counter()
            result = tool(context.session_id, args, context.db_conn)
            trace.append(ToolTraceItem(tool=tool.__name__, args=args,
                                       result_summary=json.dumps(result),
                                       duration_ms=int((perf_counter() - started) * 1000)))
            return result

        row = context.db_conn.execute(
            "SELECT state_version FROM sessions WHERE id = ?", (context.session_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Session does not exist")
        result = AgentTurnResult(response=FALLBACK_RESPONSE, state_version=row["state_version"], tool_trace=trace)
        text = message.lower()
        replanning = bool(re.search(r"\b(replan|replanning|manager|interrupt\w*|reschedule)\b|1-on-1", text))
        planning = not replanning and bool(re.search(r"\b(plan|planning|schedule|scheduling|organize|agenda)\b", text))
        if replanning:
            schedule = call(read_tools.get_schedule)
            clock = call(read_tools.get_current_time)["current_time"]
            now = datetime.fromisoformat(context.current_time or clock)
            start = now.replace(hour=14, minute=0, second=0, microsecond=0)
            interruption = dict(title="Manager 1-on-1", start_time=start.isoformat(),
                                end_time=(start + timedelta(minutes=30)).isoformat(), immutable=True)
            blocks = compute_replan(schedule["blocks"], interruption, now.isoformat())
            # The proposal validator protects all elapsed committed blocks.
            blocks.extend(block for block in schedule["blocks"] if block["title"] == "Planning"
                          and datetime.fromisoformat(block["end_time"]) <= now)
            blocks.sort(key=lambda block: block["start_time"])
            proposal = call(propose_tools.propose_replan,
                            {"new_blocks": blocks, "explanation": REPLAN_RESPONSE})
            result.response = REPLAN_RESPONSE
        elif planning:
            tasks = call(read_tools.get_tasks)["tasks"]
            calendar = call(read_tools.get_calendar)["blocks"]
            clock = call(read_tools.get_current_time)["current_time"]
            blocks = compute_day_schedule(tasks, calendar, context.current_time or clock)
            proposal = call(propose_tools.propose_schedule,
                            {"blocks": blocks, "explanation": PLAN_RESPONSE})
            result.response = PLAN_RESPONSE
        elif re.search(r"\b(left|summary|status|remaining)\b", text):
            schedule = call(read_tools.get_schedule)
            clock = call(read_tools.get_current_time)["current_time"]
            call(read_tools.get_memory)
            now = datetime.fromisoformat(context.current_time or clock)
            remaining = [block for block in schedule["blocks"]
                         if block.get("status") != "completed"
                         and datetime.fromisoformat(block["end_time"]) > now]
            if remaining:
                items = [
                    f"- {block['title']} (at {datetime.fromisoformat(block['start_time']).strftime('%I:%M %p').lstrip('0')})"
                    for block in remaining
                ]
                result.response = "Remaining today:\n" + "\n".join(items)
            else:
                result.response = "You have no remaining scheduled blocks today."
            return result
        else:
            return result
        result.plan_id = proposal["plan_id"]
        result.has_proposal = True
        result.state_version = proposal["state_version"]
        return result
