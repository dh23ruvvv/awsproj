# FlowPilot — Test, Demo & Submission

## 1. Test Strategy

### 1.1 Tool Unit Tests (`tests/test_tools.py`)

| Test | Verifies |
|---|---|
| `test_get_tasks_returns_seeded` | Seeded session returns 5 tasks matching `docs/01_PRODUCT_SPEC.md` seed state |
| `test_get_tasks_filter_status` | Optional `status` filter returns only matching tasks |
| `test_get_calendar_returns_seeded` | Seeded session returns 2 immutable blocks |
| `test_get_current_time_injectable` | Returns `FLOWPILOT_DEMO_TIMESTAMP` when set, real time otherwise |
| `test_get_schedule_empty_before_commit` | No committed blocks initially |
| `test_get_memory_empty_initially` | No memory entries on fresh session |
| `test_registry_rejects_unknown_tool` | Unknown tool name raises `ToolNotFoundError` |
| `test_registry_validates_args_schema` | Invalid args rejected per JSON Schema |

### 1.2 Engine Tests (`tests/test_engine.py`)

| Test | Verifies |
|---|---|
| `test_scheduler_golden_turn1` | Produces golden demo Turn 1 schedule for seeded state |
| `test_validator_rejects_overlap` | Overlapping blocks fail validation |
| `test_validator_rejects_completed_move` | Proposals modifying completed blocks fail |
| `test_validator_rejects_deadline_miss` | Tasks scheduled past deadline fail |
| `test_differ_kept_blocks` | Unchanged blocks categorized as `kept` |
| `test_differ_moved_blocks` | Rescheduled blocks show old and new start |
| `test_differ_shortened_blocks` | Duration changes captured with minutes |
| `test_differ_added_blocks` | New blocks in `added` |

### 1.3 API Agent-Loop Tests (`tests/test_agent_loop.py`)

| Test | Verifies |
|---|---|
| `test_turn1_message_to_proposal` | `POST /agent/message` → PROPOSED plan with tool trace |
| `test_confirm_executes_plan` | `POST /plans/{pid}/confirm` → EXECUTED, blocks in DB, tasks updated |
| `test_turn2_replan_preserves_completed` | Replan keeps completed blocks immutable, diff correct |
| `test_session_restore` | New request on same session returns committed schedule + memory |
| `test_full_golden_cycle` | Turn 1 → confirm → Turn 2 → confirm → restore (deterministic) |

### 1.4 Golden Smoke Test (`tests/test_golden_smoke.py`, `scripts/smoke.ps1`)

One command: `python -m pytest tests/test_golden_smoke.py -v`

Covers three modes:
- **Deterministic:** assert exact golden demo responses, exact DB mutations, exact diff
- **Live (invariant-based):** assert 7 invariants (see `docs/01_PRODUCT_SPEC.md` §Live-LLM Acceptance)
- **Fallback:** force timeout → verify `degraded: true`, mode badge change, valid response

### 1.5 Security Tests

| Test File | Verifies |
|---|---|
| `tests/test_injection.py` | Seeded injection note (`"ignore previous instructions…"`) has no effect — no unauthorized tool calls, no data mutation |
| `tests/test_idempotency.py` | Second `confirm` on same plan returns `already_executed: true`, no duplicate blocks in DB |
| `tests/test_stale_plan.py` | Propose → external state change → confirm returns 409 `STALE_PLAN` |

### 1.6 Frontend Checks

- **Build & typecheck:** `cd frontend; npm run build; npx tsc --noEmit` (automated)
- **Human visual checklist** (≤ 5 minutes):
  1. Type a message → response appears, plan preview with diff renders
  2. Click Confirm → timeline updates, memory pill appears
  3. Type interruption → replan diff shows kept/moved/shortened
  4. Confirm replan → timeline reflects changes, completed blocks greyed
  5. Reload page → schedule persists, memory indicator visible

## 2. Quality Gates

### Gate 1: MVP CODE COMPLETE

```powershell
# All must pass
python -m pytest tests/ -v --tb=short
cd frontend; npm run build; npx tsc --noEmit
npm run contract:check
```

Criteria: all tests green, frontend builds, types in sync.

### Gate 2: DEMO READY

```powershell
npm run smoke                    # Golden smoke test passes
python -m pytest tests/test_injection.py tests/test_idempotency.py tests/test_stale_plan.py -v
```

Criteria: smoke passes, security tests pass, Human visual checklist passes.

### Gate 3: SUBMISSION READY

Criteria: Gate 2 + all items in §6 pre-submission audit pass.

## 3. Budget Results Table

| Target | How Measured | Measured Result |
|---|---|---|
| Cold start ≤ 15s | `Measure-Command { npm run dev }` to first 200 response | _pending_ |
| Non-LLM API p95 ≤ 200ms | 10 sequential `GET /sessions/{sid}/schedule` calls | _pending_ |
| Deterministic turn ≤ 1.5s | `test_golden_smoke.py` timing assertions | _pending_ |
| Live turn p95 ≤ 10s | 5 live turns, p95 | _pending_ |
| Fallback recovery ≤ timeout+1s | Forced timeout in test | _pending_ |
| Confirm = 1 click | Human checklist | _pending_ |
| Reset+seed ≤ 2s | `Measure-Command { npm run seed }` | _pending_ |
| Clone-to-ready ≤ 10min | Fresh clone + install + start | _pending_ |
| Already-installed ≤ 60s | `npm run dev` from existing install | _pending_ |
| Video 150–170s | Recording duration | _pending_ |

> Fill `_pending_` with measured values during TASK-020 and TASK-024.

## 4. Video Claim Map

| # | Claim | Mandatory | Task IDs | Verification Step |
|---|---|---|---|---|
| V1 | FlowPilot turns messy tasks into a concrete time-block schedule | yes | TASK-008, TASK-011, TASK-019 | Smoke test Turn 1 |
| V2 | User confirms the proposed schedule with one click | yes | TASK-010, TASK-017, TASK-019 | Smoke test confirm |
| V3 | When an interruption arrives, FlowPilot replans around completed work | yes | TASK-009, TASK-011, TASK-019 | Smoke test Turn 2 |
| V4 | Completed blocks are preserved and immutable | yes | TASK-008, TASK-009 | `test_golden_smoke.py` invariant |
| V5 | Schedule diff shows kept/moved/shortened/dropped | yes | TASK-008, TASK-017 | Visual in demo |
| V6 | Cross-session memory (remembered preferences) | yes | TASK-010, TASK-018 | Reload in demo shows memory pill |
| V7 | Tool trace shows agent reasoning | yes | TASK-012, TASK-018 | Expand tool trace in demo |
| V8 | Provider mode badge always visible | yes | TASK-018, TASK-019 | Badge on screen throughout |
| V9 | Simulated Alexa+ experience (stated honestly) | yes | all BUILD | Track statement in narration |
| V10 | Live LLM integration (if completed) | optional | TASK-015 | Show "Live model" badge |
| V11 | Voice input | optional | TASK-P1-001 | Speak to UtteranceBar |

### Video Script (≤ 170s hard cap)

**0:00–0:15 — Hook (problem & value):**
> "After an interruption — your meeting moves, a task overruns — you spend 15 minutes re-deciding what to do next. FlowPilot is an ambient AI agent that builds your time-block schedule and replans instantly when life changes."

**0:15–0:30 — Setup:**
> Show the FlowPilot interface. Show seeded tasks (report, PR review, gym, groceries). Show the existing calendar blocks (standup, lunch). Point out the mode badge.

**0:30–0:55 — Turn 1 (plan):**
> Type: "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting." → Agent proposes schedule. Show plan preview card with time blocks. Point out the response line.

**0:55–1:05 — Confirm:**
> Click Confirm. Timeline updates. Point out "Remembered: morning focus blocks" memory pill. Point out tool trace (collapsible).

**1:05–1:35 — Turn 2 (interrupt & replan):**
> Type: "My manager just scheduled a 1-on-1 at 2 PM for 30 minutes — replan around it." → Agent shows diff: completed blocks kept ✓, report moved →, buffer shortened ↓. Emphasize that completed blocks are immutable and greyed.

**1:35–1:45 — Confirm replan:**
> Click Confirm. Timeline updates. Schedule still meets 5 PM deadline.

**1:45–2:05 — Session restore:**
> Reload the page. Schedule persists. Memory indicator shows remembered preferences. Type "What's left?" → Agent summarizes remaining blocks.

**2:05–2:25 — Technical highlights:**
> "FlowPilot uses [deterministic scheduling / live Gemini AI] with real database-backed tools — not generated text. The scheduling engine is pure code. The LLM chooses tools; code enforces constraints. Completed work is always preserved."

**2:25–2:40 — Track alignment & close:**
> "This is a simulated Alexa+ ambient experience [state exactly what is simulated vs real MCP]. Built for the Build, Ship, Shape hackathon. Source code and testing instructions are in the repo."

**Total: ~160s**

### Human Recording Steps

1. Start screen recorder (OBS or built-in). Resolution: 1920×1080, 30fps.
2. Open FlowPilot in browser, full window. Seed a fresh session (`npm run seed`).
3. Follow the video script above. Speak the narration or add voiceover.
4. Keep pace steady — rehearsal timing ≤ 170s.
5. Export as MP4. Upload to YouTube (unlisted or public) or Loom.
6. Verify public link works in incognito.

## 5. Devpost Kit

### Project Title
FlowPilot — Ambient AI Scheduling Agent

### Short Description
An ambient AI agent that turns messy tasks into a concrete time-block schedule and instantly replans when life interrupts — so you never re-decide what to do next.

### What it does
FlowPilot converts a jumbled list of tasks, deadlines and calendar commitments into an optimised time-block schedule. When an interruption arrives — a meeting moves, a task overruns — FlowPilot replans around what you already completed. Completed work is immutable. The diff shows exactly what kept, moved, shortened or dropped, and why. One-click confirmation commits the plan.

### How we built it
- **Backend:** Python (FastAPI) with SQLite for transactional state. Deterministic scheduling engine for constraint-based planning. Gemini API for live agent reasoning with automatic fallback.
- **Frontend:** React + TypeScript (Vite). Echo-Show-style ambient display, not a chat transcript.
- **Agent architecture:** Tools are tiered (READ / PROPOSE / COMMIT). The LLM proposes; deterministic code validates and executes. Human confirmation is required for all state-changing actions.
- **Contract integrity:** OpenAPI schema generated from backend models. Frontend types generated from OpenAPI. Drift checked automatically.

### Challenges we ran into
_Derived from `docs/07_FRICTION_LOG.md` at submission time._

### Accomplishments we're proud of
- Interrupt-and-Recover replanning with immutable completed blocks
- Deterministic scheduling engine that enforces constraints (no overlaps, deadlines, priorities)
- Graceful provider fallback with honest mode disclosure

### What we learned
_Derived from friction log and development experience._

### What's next
- Real calendar integration (Google Calendar, Outlook)
- Voice-first interaction for truly ambient use
- Multi-device sync for Echo Show deployment

### Built with
`python`, `fastapi`, `sqlite`, `react`, `typescript`, `vite`, `gemini-api`, `pydantic`

### Testing Instructions
```
# Prerequisites: Python 3.12+, Node 20+, Git

git clone <repo-url>
cd flowpilot

# Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..

# Start (both services)
npm run dev

# Seed demo data
npm run seed

# Open http://localhost:5173 in browser
# Follow the golden demo: type the utterances from the video

# Run tests
python -m pytest tests/ -v
npm run smoke
```

### Product Feedback
_Derived from `docs/07_FRICTION_LOG.md` at submission time. Includes real friction encountered with Amazon/Alexa+ tooling, MCP transport, and agentic coding tools._

## 6. Pre-Submission Audit

Run at T-6h (Oct 23, 18:30 IST). Every item must pass.

| # | Check | Command / Action | Pass |
|---|---|---|---|
| A1 | No secrets in committed files | `git log --all -p \| Select-String -Pattern "AIzaSy\|sk-\|AKIA" -SimpleMatch` | ☐ |
| A2 | `.env` is gitignored | `git status --ignored \| Select-String ".env"` | ☐ |
| A3 | LICENSE exists and is MIT | `Get-Content LICENSE -Head 3` | ☐ |
| A4 | README quickstart works | Fresh clone → follow steps → app runs | ☐ |
| A5 | Smoke test passes | `npm run smoke` | ☐ |
| A6 | Frontend builds clean | `cd frontend; npm run build` exits 0 | ☐ |
| A7 | Contract check passes | `npm run contract:check` exits 0 | ☐ |
| A8 | All content in English | Manual scan of README, Devpost kit, video script | ☐ |
| A9 | Screenshots exist | At least 2 screenshots in repo/submission | ☐ |
| A10 | Video link is public | Open in incognito browser | ☐ |
| A11 | Repo accessible to judges | Open repo URL in incognito | ☐ |
| A12 | Track claim consistent | Check "simulated Alexa+" stated in: `docs/00_PROJECT_CONTEXT.md`, `docs/01_PRODUCT_SPEC.md`, README, Devpost, video | ☐ |
| A13 | Video ≤ 180s | Check duration | ☐ |
| A14 | Claims match video claim map | Cross-reference each V1–V11 | ☐ |
