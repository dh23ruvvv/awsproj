# FlowPilot — Project Context

> Single entry point. Read this first, then the document it points you to.

## Hackathon

- **Event:** Build, Ship, Shape — Amazon Developer Hackathon 2026, Alexa+ Track, solo.
- **Deadline:** Oct 24, 2026 00:30 IST (Oct 23, 2026 12:00 PM PDT).
- **Runway at planning time:** ~52 h → **Full scope profile**.

## Product (one sentence)

**FlowPilot** is an ambient AI scheduling agent that builds concrete time-block plans from messy tasks, and when life interrupts, instantly replans around what already happened — so you never re-decide what to do next.

## Chosen Approach

- **Track approach:** C — hybrid. Primary eligibility via **Approach B** (simulated Alexa+ experience). MCP server is P1.
- **Stack:** Python 3.14 (FastAPI + Pydantic + stdlib sqlite3) backend, React + TypeScript (Vite) frontend. Single-process serving in production (FastAPI mounts built frontend).
- **Live LLM:** Gemini (API key verification is an early Human task). Deterministic provider is the default mode.

## Golden Rule

A finishable, demo-reliable product beats a complex, broken one.

## Document Index

| File | Governs |
|---|---|
| `docs/01_PRODUCT_SPEC.md` | Product pitch, surface design, golden demo scenario, scope tiers |
| `docs/02_ARCHITECTURE.md` | **Authoritative contract.** Components, DB schema, tool registry, API endpoints, state machine, sequence diagrams, security, budgets |
| `docs/03_MASTER_PLAN.md` | Backwards schedule, milestones, freeze/submission timeline, MVSP, cut-down ladder |
| `docs/04_TASK_BOARD.md` | Actionable tasks with owners, specs, acceptance, verification |
| `docs/05_AGENT_PROTOCOL.md` | Gemini and Codex operating rules, handoff format, verification, failure ladder |
| `docs/06_TEST_DEMO_SUBMISSION.md` | Test strategy, gates, video script, Devpost kit, pre-submission audit |
| `docs/07_FRICTION_LOG.md` | Real friction events with evidence |
| `docs/08_RISKS.md` | Top risks with mitigations and fallbacks |
| `docs/09_DECISIONS.md` | ADRs and runtime decisions |
| `README.md` | Public-facing: quickstart, track alignment, mode statements |
| `AGENTS.md` | Pointer file for agents (≤10 lines) |
| `.env.example` | Environment variable template |

## Environment (Verified)

- Windows, PowerShell 5.1
- Python 3.14.6, Node 24.16.0, npm 12.2.0, Git 2.52.0
- Codex CLI installed at `C:\Users\dhruv\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`
- No Docker, no Kubernetes, near-zero budget
