# FlowPilot — Architecture Decision Records

## ADR-001: Concept Tournament

**Date:** 2026-10-21
**Status:** Accepted

### Candidates

| Criterion (1–5) | FlowPilot: Interrupt-and-Recover Planning | AuraGuard: Ambient Home Safety Agent | MealWeaver: Adaptive Meal Planning Agent |
|---|---|---|---|
| Tech Implementation | 5 — real scheduling engine, multi-tool state, transactional commits | 3 — sensor simulation, limited tool depth | 4 — recipe DB, substitution engine, nutritional constraints |
| Design | 5 — ambient schedule surface, not a chat; visual diff, timeline | 3 — alert dashboard, less interactive | 4 — meal calendar, shopping list, but similar to existing apps |
| Potential Impact | 5 — universal pain: "what do I do next after disruption?" | 3 — niche: needs smart-home setup context | 3 — meal planning exists (Mealime, Eat This Much) |
| Quality of Idea | 5 — multi-step replan with immutable history is novel for voice | 3 — monitoring + alerts is well-trodden | 3 — constraint-based meal planning is explored territory |
| **Total** | **20** | **12** | **14** |

### Pass/Fail Gates

| Gate | FlowPilot | AuraGuard | MealWeaver |
|---|---|---|---|
| P0 buildable within runway | ✓ | ✓ | ✓ |
| Reliably demoable ≤ 3 min | ✓ | ✓ | ✓ |
| Real stateful tool execution | ✓ (scheduler + DB) | ✗ (simulated sensors) | ✓ (recipe DB) |
| Not a chatbot/to-do app | ✓ (schedule surface + replan) | ✓ | ✗ (borderline to-do) |

**Decision:** FlowPilot wins with score 20/20 and passes all gates. AuraGuard fails the real-tool-execution gate (sensor data would be mocked). MealWeaver fails the not-a-to-do-app gate (meal plan ≈ task list with ingredients).

**Product name:** FlowPilot

## ADR-002: Track Approach

**Date:** 2026-10-21
**Status:** Accepted

### Evaluation

| Criterion | A (MCP only) | B (simulation only) | C (hybrid) |
|---|---|---|---|
| Eligibility clarity | Medium — must implement full `2025-11-25` spec correctly | High — explicitly permitted | High — B is the primary basis |
| Judging pillar coherence | Strong for Tech Implementation | Strong for Design + Impact | Best of both |
| Hours cost of correct MCP | 6–10h (Streamable HTTP, JSON-RPC, headers, validation) | 0h | 2–4h (MCP as P1) |
| Demo risk | High — MCP transport issues are common friction point | Low — fully controlled | Low — B demo works regardless of MCP status |
| Honesty | Must work or not claim it | Clearly stated as simulation | Clear: "simulated experience with optional MCP integration" |

**Decision:** **Approach C (hybrid)**. Primary eligibility via Approach B (simulated Alexa+ experience). MCP server is P1, using the same tool registry. If MCP is not completed, submission honestly states "simulated experience" without MCP claims.

## ADR-003: Stack Choice

**Date:** 2026-10-21
**Status:** Accepted

| Criterion | Python (FastAPI) + React (Vite) | Node (Express) + React (Vite) |
|---|---|---|
| Runtimes installed | Python 3.14 ✓, Node 24 ✓ | Node 24 ✓ |
| Gemini/Codex reliability | FastAPI is idiomatic Python, strong Codex support | Good but less structured |
| SQLite on Windows | stdlib `sqlite3` — zero install, no native modules | `better-sqlite3` requires native build toolchain |
| Contract drift prevention | FastAPI + Pydantic auto-generates OpenAPI | Manual or via decorators |
| Native module risk | None (stdlib sqlite3, no binary deps) | `better-sqlite3` requires C++ compiler |
| Single-process serving | FastAPI mounts static files at `/` | Express static middleware |

**Decision:** Python (FastAPI + Pydantic + stdlib sqlite3) backend, React + TypeScript (Vite) frontend. Zero native module risk. Contract integrity via auto-generated OpenAPI.

## ADR-004: Provider Strategy

**Date:** 2026-10-21
**Status:** Accepted

Three distinct provider types:

1. **Deterministic** (default): rule-based, no network, exact golden demo responses. Uses the real scheduler engine against real DB state. Always available.
2. **Gemini** (live): `google-genai` SDK, `gemini-2.0-flash` or best available free-tier model. Timeout 15s, 1 retry on 5xx/timeout, no retry on 429, 1 repair on malformed args, circuit breaker (2 failures → 60s cooldown), fallback to deterministic with `degraded: true`.
3. **Offline fixtures**: recorded responses for test harness only, no network. Stored in `tests/fixtures/`.

The UI always shows a mode badge. The deterministic provider is never represented as autonomous reasoning.

## ADR-005: Mini-Challenge Disposition

**Date:** 2026-10-21
**Status:** Accepted

- **Friction Log bonus (+10%):** ACCEPT. Low effort — log real friction as it occurs in `docs/07_FRICTION_LOG.md`.
- **AWS Builder mini-challenge:** SKIP. Promotional credits exhausted. No paid AWS services used. A P2 adapter is allowed only if zero-cost and cannot affect P0.
- **Open Source mini-challenge:** SKIP. Effort does not justify return within runway.

---

## Runtime Decisions

_Gemini appends dated entries below as implementation proceeds._

| Date | Decision | Rationale |
|---|---|---|
| 2026-10-21 | AGENT_MODE: DIRECT | Codex CLI (`codex exec`) tested non-interactively with `--dangerously-bypass-approvals-and-sandbox`. Successfully created `handoff/codex_ping.txt` in 91ms and verified content. Automated CLI delegation verified. |
