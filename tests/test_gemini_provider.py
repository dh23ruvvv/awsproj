"""Exercise Gemini tool execution and failover offline, with an optional real call."""

import asyncio
import os
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types
from fastapi.testclient import TestClient

from server.config import settings
from server.database import SCHEMA, get_connection, seed_session
from server.main import app
from server.providers.base import AgentContext, AgentTurnResult
from server.providers.deterministic import DeterministicProvider
from server.providers.fallback import FallbackProvider
from server.providers.gemini import GeminiProvider
from server.routers import agent


@pytest.fixture
def context():
    """Provide an isolated seeded session using the real schema and tool handlers."""
    db = get_connection(":memory:")
    db.executescript(SCHEMA)
    timestamp = "2026-10-22T09:00:00+05:30"
    db.execute("INSERT INTO sessions (id, created_at, demo_timestamp) VALUES (?, ?, ?)",
               ("session", timestamp, timestamp))
    seed_session(db, "session")
    db.commit()
    yield AgentContext("session", db, timestamp)
    db.close()


def response(name=None, args=None, text="Ready."):
    """Build actual SDK response objects to preserve function-call wire semantics."""
    part = (types.Part(function_call=types.FunctionCall(name=name, args=args)) if name
            else types.Part.from_text(text=text))
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[part]))])


@pytest.fixture
def sdk(monkeypatch):
    """Replace only the network boundary while retaining SDK request validation."""
    from server.providers import gemini

    generate = AsyncMock()
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    manager = AsyncMock()
    manager.__aenter__.return_value = client
    constructor = lambda **kwargs: SimpleNamespace(aio=manager)
    monkeypatch.setattr(gemini.genai, "Client", constructor)
    return generate


def test_tool_execution_and_prompt(context, sdk):
    """Persist a real proposal and send validated results back to the model."""
    sdk.side_effect = [response("get_tasks", {}), response("propose_schedule", {
        "blocks": [], "explanation": "Schedule the required tasks."}), response()]
    result = asyncio.run(GeminiProvider().run_agent_turn("Plan <my> day", context))
    assert result.provider_used == "gemini" and not result.degraded
    assert result.response == "Ready." and result.has_proposal and result.plan_id
    assert [item["tool"] for item in result.tool_trace] == ["get_tasks", "propose_schedule"]
    assert all(item["duration_ms"] >= 0 for item in result.tool_trace)
    assert context.db_conn.execute("SELECT status FROM plans WHERE id = ?",
                                   (result.plan_id,)).fetchone()[0] == "PROPOSED"
    assert context.db_conn.execute("SELECT state_version FROM sessions").fetchone()[0] == 1
    config = sdk.call_args.kwargs["config"]
    assert context.current_time in config.system_instruction
    assert "immutable" in config.system_instruction
    assert "commit_schedule" not in [t.name for t in config.tools[0].function_declarations]
    contents = sdk.call_args.kwargs["contents"]
    assert "<user_input>Plan &lt;my&gt; day</user_input>" in contents[0].parts[0].text
    assert contents[2].parts[0].function_response.response["tasks"]


def test_repair_malformed_arguments(context, sdk):
    """One schema error is returned to Gemini and a corrected call executes."""
    sdk.side_effect = [response("get_tasks", {"unknown": True}),
                       response("get_tasks", {}), response()]
    result = asyncio.run(GeminiProvider().run_agent_turn("Tasks?", context))
    assert not result.degraded and sdk.await_count == 3
    assert "validation_error" in result.tool_trace[0]["result_summary"]
    assert "tasks" in result.tool_trace[1]["result_summary"]
    assert "validation_error" in sdk.call_args.kwargs["contents"][2].parts[0].function_response.response


def test_repeated_bad_args_fall_back(context, sdk):
    """A second invalid tool call exhausts repair and returns deterministic output."""
    sdk.side_effect = [response("get_tasks", {"unknown": True})] * 2
    provider = FallbackProvider(GeminiProvider(), DeterministicProvider())
    result = asyncio.run(provider.run_agent_turn("hello", context))
    assert result.degraded and result.provider_used == "gemini-fallback"
    assert sdk.await_count == 2 and provider.failure_count == 1


@pytest.mark.parametrize("name", ["commit_schedule", "delete_everything"])
def test_unauthorized_tools_cannot_execute(context, sdk, name):
    """Even fabricated function calls cannot commit or delete domain data."""
    sdk.side_effect = [response(name, {})] * 2
    result = asyncio.run(FallbackProvider(GeminiProvider(), DeterministicProvider()).run_agent_turn("hello", context))
    assert result.degraded
    assert context.db_conn.execute("SELECT state_version FROM sessions").fetchone()[0] == 1
    assert context.db_conn.execute("SELECT count(*) FROM plans").fetchone()[0] == 0


def test_breaker_cooldown_and_recovery(context, monkeypatch):
    """Two failures open the circuit; cooldown expiry probes and success resets it."""
    from server.providers import fallback

    now = [100.0]
    monkeypatch.setattr(fallback.time, "time", lambda: now[0])
    primary = SimpleNamespace(run_agent_turn=AsyncMock(side_effect=[
        TimeoutError(), RuntimeError("API failure"), AgentTurnResult("Recovered", provider_used="gemini")]))
    provider = FallbackProvider(primary, DeterministicProvider())
    for _ in range(2):
        result = asyncio.run(provider.run_agent_turn("hello", context))
        assert result.degraded and result.provider_used == "gemini-fallback"
    now[0] = 159.999
    assert asyncio.run(provider.run_agent_turn("hello", context)).degraded
    assert primary.run_agent_turn.await_count == 2 and provider.failure_count == 2
    now[0] = 160.0
    result = asyncio.run(provider.run_agent_turn("hello", context))
    assert result.response == "Recovered" and not result.degraded
    assert provider.failure_count == 0 and primary.run_agent_turn.await_count == 3


def test_success_resets_consecutive_failures(context):
    """A successful primary turn breaks a sequence of failures."""
    primary = SimpleNamespace(run_agent_turn=AsyncMock(side_effect=[
        RuntimeError(), AgentTurnResult("OK"), RuntimeError()]))
    provider = FallbackProvider(primary, DeterministicProvider())
    for _ in range(3):
        asyncio.run(provider.run_agent_turn("hello", context))
    assert provider.failure_count == 1


def test_timeout_budget_and_real_deterministic_proposal(context, sdk, monkeypatch):
    """A stalled API retries once and falls back within the total timeout plus one second."""
    async def stall(**kwargs):
        """Simulate a network operation that never returns before cancellation."""
        await asyncio.sleep(10)

    sdk.side_effect = stall
    monkeypatch.setattr(settings, "flowpilot_llm_timeout_s", 0.1)
    started = perf_counter()
    result = asyncio.run(FallbackProvider(GeminiProvider(), DeterministicProvider()).run_agent_turn("Plan my day", context))
    assert perf_counter() - started < 1.1
    assert result.degraded and result.provider_used == "gemini-fallback"
    assert result.has_proposal and result.plan_id and sdk.await_count == 2


@pytest.mark.parametrize("code,attempts", [(429, 1), (400, 1), (503, 2)])
def test_api_retry_policy(context, sdk, code, attempts):
    """Retry only transient server errors, never rate limits or bad requests."""
    class APIError(Exception):
        """Carry the status code exposed by SDK errors."""

    error = APIError("API failure")
    error.code = code
    sdk.side_effect = error
    result = asyncio.run(FallbackProvider(GeminiProvider(), DeterministicProvider()).run_agent_turn("hello", context))
    assert result.degraded and sdk.await_count == attempts


def test_transient_error_recovers(context, sdk):
    """A successful retry preserves live mode."""
    sdk.side_effect = [TimeoutError(), response()]
    result = asyncio.run(GeminiProvider().run_agent_turn("hello", context))
    assert not result.degraded and sdk.await_count == 2


def test_router_selection_and_shared_breaker(tmp_path, monkeypatch):
    """Exercise default, header/query overrides and breaker persistence through HTTP."""
    monkeypatch.setattr(settings, "flowpilot_db_path", str(tmp_path / "router.db"))
    monkeypatch.setattr(settings, "flowpilot_default_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(agent, "_message_times", {})
    from server.providers import gemini

    primary = AsyncMock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(gemini.GeminiProvider, "run_agent_turn", primary)
    agent._live_provider.cache_clear()
    try:
        with TestClient(app) as client:
            sid = client.post("/api/v1/sessions", json={"seed": True}).json()["session_id"]
            url = f"/api/v1/sessions/{sid}/agent/message"
            for _ in range(3):
                assert client.post(url, json={"message": "hello"}).json()["degraded"]
            assert primary.await_count == 2
            assert client.post(url, headers={"X-FlowPilot-Provider": "deterministic"},
                               json={"message": "hello"}).json()["provider_used"] == "deterministic"
            assert client.post(url + "?provider=deterministic", headers={"X-FlowPilot-Provider": "gemini"},
                               json={"message": "hello"}).json()["provider_used"] == "deterministic"
            monkeypatch.setattr(settings, "flowpilot_default_provider", "deterministic")
            assert client.post(url + "?provider=gemini", json={"message": "hello"}).json()["degraded"]
            monkeypatch.setattr(settings, "gemini_api_key", None)
            monkeypatch.delenv("GEMINI_API_KEY", raising=False)
            assert client.post(url + "?provider=gemini", json={"message": "hello"}).json()["provider_used"] == "deterministic"
    finally:
        agent._live_provider.cache_clear()


@pytest.mark.skipif(not (settings.gemini_api_key or os.getenv("GEMINI_API_KEY")), reason="GEMINI_API_KEY is absent")
def test_live_gemini(context):
    """Use real inference and require a real read tool call when a key is supplied."""
    result = asyncio.run(GeminiProvider().run_agent_turn(
        "Call get_tasks to check my task list, then briefly summarize the tasks. Do not propose changes.", context))
    assert result.response and result.provider_used == "gemini" and not result.degraded
    assert any(item["tool"] == "get_tasks" for item in result.tool_trace)
