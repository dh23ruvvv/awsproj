"""Deterministic failover with a shared, time-based circuit breaker."""

import time
import sqlite3

from .base import AgentContext, AgentTurnResult, Provider


class FallbackProvider:
    """Skip the primary for sixty seconds after two consecutive failed turns."""

    def __init__(self, primary: Provider, fallback: Provider) -> None:
        """Retain providers and circuit state across requests."""
        self.primary = primary
        self.fallback = fallback
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def run_agent_turn(self, message: str, context: AgentContext) -> AgentTurnResult:
        """Run the primary when healthy and label every fallback response."""
        if self.failure_count < 2 or time.time() - self.last_failure_time >= 60.0:
            context.db_conn.execute("SAVEPOINT primary_provider")
            try:
                result = await self.primary.run_agent_turn(message, context)
            except (ValueError, sqlite3.OperationalError):
                # Domain refusals and concurrency conflicts are not provider outages.
                context.db_conn.execute("ROLLBACK TO SAVEPOINT primary_provider")
                context.db_conn.execute("RELEASE SAVEPOINT primary_provider")
                raise
            except Exception:
                context.db_conn.execute("ROLLBACK TO SAVEPOINT primary_provider")
                context.db_conn.execute("RELEASE SAVEPOINT primary_provider")
                self.failure_count += 1
                self.last_failure_time = time.time()
            else:
                context.db_conn.execute("RELEASE SAVEPOINT primary_provider")
                self.failure_count = 0
                return result
        result = await self.fallback.run_agent_turn(message, context)
        result.degraded = True
        result.provider_used = "gemini-fallback"
        return result
