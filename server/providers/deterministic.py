"""Offline intent routing through real read tools and scheduling proposals."""

import json
import re
from datetime import datetime, timedelta
from time import perf_counter

from server.engine.scheduler import compute_day_schedule, compute_replan
from server.tools import read_tools, propose_tools
from server.tools.preferences import remember_preference
from .base import AgentContext, AgentTurnResult, ToolTraceItem

PLAN_RESPONSE = "I prepared a proposal from your saved tasks and calendar. Review the changes, then confirm to save them."
REPLAN_RESPONSE = "I prepared a proposal around your interruption, preserving protected commitments. Review the changes, then confirm to save them."
FALLBACK_RESPONSE = "Deterministic mode supports 'Plan my day', 'What's left?', and interruptions such as 'Replan around a meeting from 2:00 to 2:45 PM'. Add or edit tasks using the task controls."

_CLOCK = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"


def _interruption(message: str, now: datetime) -> dict:
    """Parse one same-day interval; never guess missing times or dates."""
    if re.search(r"\b(tomorrow|yesterday|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\d{4}-\d{2}-\d{2}|\b(?:utc|gmt|pst|pdt|ist|est|edt)\b", message, re.I):
        raise ValueError("Deterministic mode accepts times today in the session timezone only.")
    ranges = list(re.finditer(r"\bfrom\s+" + _CLOCK + r"\s*(?:to|until|[-–])\s*" + _CLOCK + r"\b", message, re.I))
    durations = list(re.finditer(r"\bat\s+" + _CLOCK + r"\s+for\s+(\d+)\s*(minutes?|mins?)\b", message, re.I))
    if len(ranges) + len(durations) != 1:
        raise ValueError("Give one interruption with explicit times, for example: 'Replan around a meeting from 2:00 to 2:45 PM'.")

    def clock(hour, minute, meridiem):
        meridiem = meridiem.lower() if meridiem else None
        hour, minute = int(hour), int(minute or 0)
        if minute > 59 or (meridiem and not 1 <= hour <= 12) or (not meridiem and not 0 <= hour <= 23):
            raise ValueError("Please use valid clock times, for example 2:00 PM to 2:45 PM.")
        if meridiem:
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if ranges:
        h1, m1, ap1, h2, m2, ap2 = ranges[0].groups()
        # A trailing AM/PM applies to both ends (2:00 to 2:45 PM).
        start = clock(h1, m1, ap1 or ap2)
        end = clock(h2, m2, ap2 or ap1)
    else:
        hour, minute, meridiem, duration, _ = durations[0].groups()
        start = clock(hour, minute, meridiem)
        end = start + timedelta(minutes=int(duration))
    if start < now or end <= start or end.date() != now.date():
        raise ValueError("The interruption must start today at or after the current time and end after it on the same day.")
    phrase = message[:(ranges or durations)[0].start()].strip(' ,.:!-')
    phrase = re.sub(r'^(?:please\s+)?(?:replan|reschedule|rework)(?:\s+(?:my|the)\s+day)?\s*(?:around|for)?\s*', '', phrase, flags=re.I)
    phrase = re.sub(r'^(?:add\s+(?:an?\s+)?(?:interruption\s*:?\s*)?|i\s+have\s+|an?\s+)', '', phrase, flags=re.I).strip(' "\'')
    if re.fullmatch(r'(?:urgent\s+|unexpected\s+)?meeting(?:\s+just\s+came\s+up)?', phrase, re.I):
        phrase = ''
    title = 'Manager 1-on-1' if re.search(r'manager|1-on-1', message, re.I) else (phrase or 'Unexpected meeting')
    if title.lower() in {'meeting', 'interruption', 'a meeting', 'an interruption'}:
        title = 'Unexpected meeting'
    return dict(title=title, start_time=start.isoformat(), end_time=end.isoformat(), immutable=True)


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
        if re.match(r'^\s*(?:please\s+)?remember\b', text):
            preference = re.sub(r'^\s*(?:please\s+)?remember\s*:?\s*', '', message, flags=re.I)
            saved = call(remember_preference, {'preference': preference})
            result.state_version = saved['state_version']
            result.response = f"Remembered for this day: {saved['entry']['value']}"
            return result
        replanning = bool(re.search(r"\b(replan|replanning|rework|manager|interrupt\w*|reschedule)\b|1-on-1", text))
        planning = not replanning and bool(re.search(r"\b(plan|planning|schedule|scheduling|organize|agenda)\b", text))
        if replanning:
            schedule = call(read_tools.get_schedule)
            clock = call(read_tools.get_current_time)["current_time"]
            now = datetime.fromisoformat(context.current_time or clock)
            try:
                interruption = _interruption(message, now)
                tasks = call(read_tools.get_tasks)['tasks']
                blocks = compute_replan(schedule["blocks"], interruption, now.isoformat(), tasks=tasks)
                proposal = call(propose_tools.propose_replan,
                                {"new_blocks": blocks, "explanation": REPLAN_RESPONSE})
            except ValueError as exc:
                result.response = f"I could not prepare a proposal: {exc} Your saved calendar is unchanged."
                return result
            result.response = REPLAN_RESPONSE
        elif planning:
            if not re.fullmatch(r"\s*(?:please\s+)?(?:plan|schedule|organize)(?:\s+(?:out\s+)?(?:my|the|for)?\s*(?:day|today|schedule))?[.!?]?\s*", text):
                result.response = "Deterministic mode plans saved tasks only. Add or edit task durations, priorities and deadlines using the task controls, then say 'Plan my day'. For an interruption, give an explicit range such as 'Replan from 2:00 to 2:45 PM'."
                return result
            tasks = call(read_tools.get_tasks)["tasks"]
            calendar = call(read_tools.get_calendar)["blocks"]
            clock = call(read_tools.get_current_time)["current_time"]
            preferences = call(read_tools.get_memory)['entries']
            try:
                blocks = compute_day_schedule(tasks, calendar, context.current_time or clock, preferences)
                proposal = call(propose_tools.propose_schedule,
                                {"blocks": blocks, "explanation": PLAN_RESPONSE})
            except ValueError as exc:
                result.response = f"I could not fit the requested work: {exc} Adjust your tasks or availability and try again. Your saved calendar is unchanged."
                return result
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
