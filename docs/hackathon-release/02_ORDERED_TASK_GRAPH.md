# FlowPilot Ordered Task Graph — Canonical Task Specifications and Dependencies

> **Purpose:** Canonical single source of truth for all engineering, design, testing, and submission tasks. Defines strict boundaries, concrete implementation steps, inputs/outputs, edge cases, tests, and rollback procedures.  
> **Last verified against commit:** `f2f2706`  
> **Status Legend:**  
> - `[VERIFIED]`: Confirmed directly in active repository source code, git history, or live environment.  
> - `[INFERRED]`: Reasoned from configuration and hackathon rules; pending execution.  
> - `[NOT RUN]`: Explicitly unexecuted in the current session.  
> - `[P0]`: Critical priority — required for shippable MVS and demo integrity.  
> - `[P1]`: High priority — completeness, polish, and error prevention.  
> - `[P2]`: Normal priority — secondary optimization or enhancement.  

---

## 1. Compact Task Index Table

| Task ID | Task Title | Owner | Priority | Estimate | Depends-On | Exclusive Edit Files | Gate |
|---|---|---|---|---|---|---|---|
| **TASK-101** | Fix Replan Collision with Immutable Blocks | Codex | P0 | 1.5h | None | `server/engine/scheduler.py` | GATE-1 |
| **TASK-102** | Flexible Focus & Task Duration Fitting | Codex | P0 | 1.5h | None | `server/engine/scheduler.py` | GATE-1 |
| **TASK-103** | Multi-Pass Free Interval Gap Placement | Codex | P0 | 1.5h | TASK-102 | `server/engine/scheduler.py` | GATE-1 |
| **TASK-104** | Lengthened Duration Classification in Differ | Codex | P1 | 1.0h | None | `server/engine/differ.py` | GATE-1 |
| **TASK-105** | Preserve Block UUIDs & Enforce Atomic Commit | Codex | P0 | 1.5h | None | `server/tools/commit_tools.py` | GATE-1 |
| **TASK-106** | Inbound State Version Validation & Rate Eviction | Codex | P1 | 1.0h | None | `server/routers/agent.py` | GATE-1 |
| **TASK-107** | Supersede Abandoned Proposals in DB | Codex | P1 | 0.5h | None | `server/tools/propose_tools.py` | GATE-1 |
| **TASK-108** | Scoped Tool Repair in Gemini Provider Loop | Codex | P1 | 1.0h | None | `server/providers/gemini.py` | GATE-1 |
| **TASK-109** | Secondary Database Indexes for Foreign Keys | Codex | P1 | 0.5h | None | `server/database.py` | GATE-1 |
| **TASK-110** | Deterministic Preference Matching Cleanup | Codex | P2 | 0.5h | None | `server/tools/commit_tools.py` | GATE-1 |
| **TASK-111** | Export OpenAPI Schema & Freeze Backend Contract | Codex | P0 | 0.5h | TASK-101..110 | `generated/openapi.json` | **GATE-2 (CONTRACT-FREEZE)** |
| **TASK-201** | Generate Frontend Types from Frozen Schema | Gemini | P0 | 0.5h | TASK-111 | `frontend/src/api/types.ts` | GATE-3 |
| **TASK-202** | Render Lengthened Duration Badges in PlanPreview | Gemini | P1 | 1.0h | TASK-201 | `frontend/src/components/PlanPreview.tsx`, `PlanPreview.css` | GATE-3 |
| **TASK-203** | Stale-State and Double-Approve Defense in UI | Gemini | P0 | 1.0h | TASK-201 | `frontend/src/App.tsx` | GATE-3 |
| **TASK-204** | Alexa+ Ambient Feedback & Interaction Polish | Gemini | P1 | 1.5h | TASK-203 | `frontend/src/components/UtteranceBar.tsx`, `App.tsx` | GATE-3 |
| **TASK-205** | Accessibility & Keyboard Navigation Hardening | Gemini | P1 | 1.0h | TASK-202 | `frontend/src/components/PlanPreview.tsx`, `TaskList.tsx` | GATE-3 |
| **TASK-301** | Full Clean-Clone & Golden Smoke Test Gate | Integrator | P0 | 1.0h | TASK-201..205 | `docs/hackathon-release/` (reporting only) | **GATE-4 (CODE-FREEZE)** |
| **TASK-302** | Record & Validate 3-Minute Demo Video | Human | P0 | 2.0h | TASK-301 | Video Artifact / YouTube link | **GATE-5 (SUBMIT)** |
| **TASK-303** | Final Devpost Package & Track Verification | Human | P0 | 1.5h | TASK-302 | Devpost Portal Submission | **GATE-5 (SUBMIT)** |

---

## 2. Canonical Task Specifications (Codex Tasks)

---

### TASK-101: Fix Replan Collision with Immutable Blocks
- **Owner:** Codex
- **Priority:** P0 (Demo Blocker)
- **Effort Estimate:** 1.5 hours
- **Linked Findings:** FLAW-003
- **Gate:** GATE-1
- **Preconditions:** Active branch `main`, clean git status. `python -m pytest tests/test_engine.py` passes.
- **Exclusive Edit Scope:** `server/engine/scheduler.py` (specifically `compute_replan` function).
- **Read-Only Scope:** `server/engine/validator.py`, `tests/test_engine.py`, `tests/test_golden_smoke.py`.
- **Implementation Steps:**
  1. Inspect `server/engine/scheduler.py:93-107`. Currently, when `cursor` (pushed by an interruption) exceeds the start of an immutable block (`left < cursor`), line 99 raises `ValueError("Replan collides with immutable block")`.
  2. Implement gap-jumping: If `left < cursor`, do NOT raise an error. Instead:
     - Keep the immutable block fixed at `[left, right]`.
     - Advance the scheduling cursor to the end of the immutable block: `cursor = max(cursor, right)`.
     - Place the displaced movable block starting at the new `cursor`.
  3. Ensure that if the shifted block encounters the `"Buffer / overflow"` block (16:00–17:00), the buffer absorbs the delay by truncating its start time (`finish = right`), preserving the 17:00 day boundary.
  4. If shifted blocks exceed `day_end` (17:00:00), truncate non-critical work or raise a descriptive, user-friendly exception rather than an unhandled crash.
- **Input / Output Contract:**
  - Input: `current_blocks: list[dict]`, `interruption: dict`, `current_time: str`.
  - Output: `list[dict]` containing valid, non-overlapping blocks satisfying `validate_schedule`.
- **Edge Cases:**
  - Interruption ends exactly when immutable block begins.
  - Back-to-back immutable blocks (e.g., 12:00–13:00 Lunch and 13:00–13:30 1-on-1). Cursor must jump both.
- **What NOT to Do:**
  - Do NOT modify the immutable block's `start_time`, `end_time`, or `title`.
  - Do NOT mutate `server/engine/validator.py`.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_engine.py tests/test_propose.py
  ```
- **Definition of Done:** `compute_replan` successfully schedules an afternoon interruption between 14:00 and 15:00 when an immutable block exists at 15:30 without throwing a collision error.
- **Rollback Action:** `git checkout server/engine/scheduler.py`.

---

### TASK-102: Flexible Focus & Task Duration Fitting
- **Owner:** Codex
- **Priority:** P0 (Core Scheduling Correctness)
- **Effort Estimate:** 1.5 hours
- **Linked Findings:** FLAW-001
- **Gate:** GATE-1
- **Preconditions:** TASK-101 completed.
- **Exclusive Edit Scope:** `server/engine/scheduler.py` (`compute_day_schedule` function).
- **Read-Only Scope:** `server/engine/validator.py`, `server/models.py`.
- **Implementation Steps:**
  1. Inspect `server/engine/scheduler.py:48-64`.
  2. Remove rigid focus task slicing `((5, 55), (135, 60), (300, 45))` and the hard failure `ValueError("Focus task exceeds available reservations")`.
  3. Instead, dynamically allocate chunks based on available free slots between existing immutable blocks (e.g. 09:05–10:00, 10:30–12:00, 13:00–16:00).
  4. Remove arbitrary 45-minute truncation of personal tasks:
     - Replace `duration = min(task["duration_minutes"], 45) if personal and not low else task["duration_minutes"]` with full requested `duration = task["duration_minutes"]`.
  5. If total pending task duration exceeds available day hours (09:00–17:00 minus immutable meetings), schedule highest-priority tasks first; mark remaining tasks as unassigned/pending without throwing an unhandled `ValueError`.
- **Input / Output Contract:**
  - Input: `tasks: list[dict]`, `calendar_blocks: list[dict]`, `current_time: str`.
  - Output: `list[dict]` of scheduled blocks with valid ISO timestamps.
- **Edge Cases:** Focus task with 180 min duration; personal task with 90 min duration.
- **What NOT to Do:** Do not change task schema or modify task database records in `compute_day_schedule`.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_engine.py -k "test_turn_one or test_diff"
  ```
- **Definition of Done:** Work tasks > 160 minutes and personal tasks > 45 minutes are scheduled into real available gaps without truncation or crash.
- **Rollback Action:** `git checkout server/engine/scheduler.py`.

---

### TASK-103: Multi-Pass Free Interval Gap Placement
- **Owner:** Codex
- **Priority:** P0 (Algorithm Robustness)
- **Effort Estimate:** 1.5 hours
- **Linked Findings:** FLAW-002
- **Gate:** GATE-1
- **Preconditions:** TASK-102 completed.
- **Exclusive Edit Scope:** `server/engine/scheduler.py` (`place` inner function).
- **Read-Only Scope:** `server/engine/validator.py`.
- **Implementation Steps:**
  1. Inspect `server/engine/scheduler.py:31-45`.
  2. Replace single-pass greedy scan with an interval gap scanner:
     - Compute all existing free intervals $[t_{start}, t_{end}]$ within `09:00:00` and `17:00:00`.
     - For each task to place, search for the earliest free interval whose duration $\ge$ task duration (or desired chunk size) and whose finish $\le$ task deadline.
     - Place the task within that interval, update the free interval list, and proceed.
  3. Re-verify the complete schedule with `validate_schedule(blocks, calendar_blocks, current_time)`.
- **Input / Output Contract:** Guaranteed non-overlapping block allocation.
- **Edge Cases:** Free gaps of varying sizes (e.g. 30m, 60m, 90m); tasks with early deadlines.
- **What NOT to Do:** Do not introduce non-deterministic sorting or random intervals.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_engine.py tests/test_propose.py
  ```
- **Definition of Done:** Dense schedules with 4+ pre-existing commitments place pending tasks without pairwise overlap.
- **Rollback Action:** `git checkout server/engine/scheduler.py`.

---

### TASK-104: Lengthened Duration Classification in Differ
- **Owner:** Codex
- **Priority:** P1 (Diff Accuracy)
- **Effort Estimate:** 1.0 hour
- **Linked Findings:** FLAW-005
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/engine/differ.py`.
- **Exclusive Edit Scope:** `server/engine/differ.py`.
- **Read-Only Scope:** `server/models.py`, `tests/test_engine.py`.
- **Implementation Steps:**
  1. Inspect `server/engine/differ.py:8, 23-26`.
  2. Add `"lengthened"` to the initialized diff dictionary:
     ```python
     result = {key: [] for key in ("kept", "moved", "shortened", "lengthened", "dropped", "added")}
     ```
  3. When `new_duration > old_duration`, append to `result["lengthened"]`:
     ```python
     if new_duration > old_duration:
         result["lengthened"].append({
             **base,
             "old_duration_min": old_duration,
             "new_duration_min": new_duration,
         })
     ```
  4. Ensure blocks whose duration increased are not classified as `kept`.
- **Input / Output Contract:**
  - Before: `result` has keys `("kept", "moved", "shortened", "dropped", "added")`.
  - After: `result` has keys `("kept", "moved", "shortened", "lengthened", "dropped", "added")`.
- **Edge Cases:** Block moved AND lengthened (appears in both `moved` and `lengthened`).
- **What NOT to Do:** Do not remove existing keys from diff output.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_engine.py -k "test_diff"
  ```
- **Definition of Done:** Extending a 30m block to 60m populates `result["lengthened"]` with old/new duration.
- **Rollback Action:** `git checkout server/engine/differ.py`.

---

### TASK-105: Preserve Block UUIDs & Enforce Atomic Commit
- **Owner:** Codex
- **Priority:** P0 (Data Integrity)
- **Effort Estimate:** 1.5 hours
- **Linked Findings:** FLAW-006, NEW-001
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/tools/commit_tools.py`.
- **Exclusive Edit Scope:** `server/tools/commit_tools.py`.
- **Read-Only Scope:** `server/database.py`, `server/models.py`, `tests/test_plans.py`.
- **Implementation Steps:**
  1. Inspect `server/tools/commit_tools.py:72-95`.
  2. When iterating over proposed `blocks`, check if `block.get("id")` is `None`:
     - If `None`, attempt to look up an existing non-completed block in the session with identical `title` or identical `task_id`.
     - If matched, reuse `old["id"]` instead of generating a new `uuid4()`.
  3. Ensure existing rows for persistent meetings (e.g. "Team Standup", "Lunch") retain their database primary keys.
  4. Wrap the execution in an explicit database transaction with atomic error rollback:
     - On any exception, execute `ROLLBACK TO SAVEPOINT commit_domain`, set plan status to `'FAILED'`, and ensure no partial calendar rows or updated task rows persist.
- **Input / Output Contract:** Calendar blocks committed to DB preserve stable primary keys across plan confirmations.
- **Edge Cases:** New task being scheduled for the first time gets fresh UUID; existing meeting retains original UUID.
- **What NOT to Do:** Never delete completed calendar blocks (`status='completed'`).
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_plans.py tests/test_idempotency.py
  ```
- **Definition of Done:** Confirming a replan does not change the primary key IDs of unchanged or moved blocks.
- **Rollback Action:** `git checkout server/tools/commit_tools.py`.

---

### TASK-106: Inbound State Version Validation & Rate Eviction
- **Owner:** Codex
- **Priority:** P1 (Concurrency & Memory Safety)
- **Effort Estimate:** 1.0 hour
- **Linked Findings:** FLAW-007, FLAW-009
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/routers/agent.py`.
- **Exclusive Edit Scope:** `server/routers/agent.py`.
- **Read-Only Scope:** `server/models.py`, `tests/test_agent_loop.py`.
- **Implementation Steps:**
  1. Inspect `server/routers/agent.py:46-82`.
  2. In `agent_message`, check `if request.state_version is not None`:
     - Query current session `state_version`.
     - If `request.state_version != current_version`:
       return `_error(409, "STALE_STATE_VERSION", f"Client state version {request.state_version} does not match current session version {current_version}")`.
  3. In `_rate_lock` block, add periodic cleanup of `_message_times`:
     - If `len(_message_times) > 1000`, prune keys whose deques are empty or older than 120s.
- **Input / Output Contract:** Stale client state rejected immediately with HTTP 409 before LLM invocation.
- **Edge Cases:** `request.state_version` omitted (allowed for initial utterance); `request.state_version` matches current.
- **What NOT to Do:** Do not block requests that omit `state_version` (`int | None = None` must remain optional).
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_agent_loop.py tests/test_stale_plan.py
  ```
- **Definition of Done:** Sending an outdated `state_version: 0` when session is at version 1 returns HTTP 409 without calling the provider.
- **Rollback Action:** `git checkout server/routers/agent.py`.

---

### TASK-107: Proposal Garbage Collection in Database
- **Owner:** Codex
- **Priority:** P1 (Data Hygiene)
- **Effort Estimate:** 0.5 hours
- **Linked Findings:** FLAW-008
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/tools/propose_tools.py`.
- **Exclusive Edit Scope:** `server/tools/propose_tools.py`.
- **Read-Only Scope:** `server/database.py`, `tests/test_propose.py`.
- **Implementation Steps:**
  1. Inspect `server/tools/propose_tools.py:47-54`.
  2. Before inserting a new row into `plans` with `status='PROPOSED'`, mark existing proposals for this session as superseded:
     ```python
     db_conn.execute(
         "UPDATE plans SET status = 'CANCELLED' WHERE session_id = ? AND status = 'PROPOSED'",
         (session_id,)
     )
     ```
  3. Proceed with inserting the new active proposal.
- **Input / Output Contract:** Only one active proposal exists with `status='PROPOSED'` per session.
- **Edge Cases:** First proposal in empty session (0 rows updated).
- **What NOT to Do:** Do not cancel plans with status `'CONFIRMED'` or `'EXECUTED'`.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_propose.py tests/test_plans.py
  ```
- **Definition of Done:** After 3 consecutive proposals, only the 3rd plan has `status='PROPOSED'`; earlier plans are `'CANCELLED'`.
- **Rollback Action:** `git checkout server/tools/propose_tools.py`.

---

### TASK-108: Scoped Tool Repair in Gemini Provider Loop
- **Owner:** Codex
- **Priority:** P1 (LLM Resilience)
- **Effort Estimate:** 1.0 hour
- **Linked Findings:** FLAW-011
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/providers/gemini.py`.
- **Exclusive Edit Scope:** `server/providers/gemini.py`.
- **Read-Only Scope:** `tests/test_gemini_provider.py`.
- **Implementation Steps:**
  1. Inspect `server/providers/gemini.py:66, 103-107`.
  2. Currently, `repaired = False` is initialized outside the 16-turn loop, meaning any second tool error crashes the turn.
  3. Replace the single global boolean with a per-tool-call or per-round repair allowance:
     - Allow up to 2 repair opportunities across the entire turn, or 1 repair per unique tool name.
     - When repair limit for that tool is reached, fallback or log gracefully instead of unhandled crash.
- **Input / Output Contract:** Agent loop tolerates a schema repair in step 1 followed by an argument repair in step 3.
- **Edge Cases:** Persistent infinite repair loop (capped at max 2 repairs total).
- **What NOT to Do:** Do not allow unbounded repair loops (max 16 iterations remains hard upper bound).
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_gemini_provider.py -k "test_repair"
  ```
- **Definition of Done:** Multi-step tool executions with minor formatting errors recover without aborting the turn.
- **Rollback Action:** `git checkout server/providers/gemini.py`.

---

### TASK-109: Database Secondary Indexes for Foreign Keys
- **Owner:** Codex
- **Priority:** P1 (Performance)
- **Effort Estimate:** 0.5 hours
- **Linked Findings:** FLAW-010
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/database.py`.
- **Exclusive Edit Scope:** `server/database.py`.
- **Read-Only Scope:** `tests/test_scaffolding.py`.
- **Implementation Steps:**
  1. Inspect `server/database.py:11-18` (`SCHEMA` string).
  2. Add secondary index creation statements to `SCHEMA`:
     ```sql
     CREATE INDEX IF NOT EXISTS idx_calendar_blocks_session ON calendar_blocks(session_id, start_time);
     CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id, status);
     CREATE INDEX IF NOT EXISTS idx_plans_session ON plans(session_id, status);
     CREATE INDEX IF NOT EXISTS idx_execution_log_session ON execution_log(session_id);
     CREATE INDEX IF NOT EXISTS idx_memory_session ON memory(session_id, key);
     ```
  3. Ensure `init_db` creates these indexes idempotently without affecting existing rows.
- **Input / Output Contract:** SQLite tables have covering indexes on `session_id` and query filters.
- **Edge Cases:** Database already seeded (IF NOT EXISTS prevents collision).
- **What NOT to Do:** Do not change table primary keys or foreign key actions (`ON DELETE CASCADE`).
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_scaffolding.py tests/test_sessions.py
  ```
- **Definition of Done:** SQLite query plans (`EXPLAIN QUERY PLAN`) use index searches rather than table scans.
- **Rollback Action:** `git checkout server/database.py`.

---

### TASK-110: Deterministic Preference Matching Cleanup
- **Owner:** Codex
- **Priority:** P2 (Code Cleanliness)
- **Effort Estimate:** 0.5 hours
- **Linked Findings:** FLAW-004
- **Gate:** GATE-1
- **Preconditions:** Clean git status on `server/tools/commit_tools.py`.
- **Exclusive Edit Scope:** `server/tools/commit_tools.py`.
- **Read-Only Scope:** `server/database.py`.
- **Implementation Steps:**
  1. Inspect `server/tools/commit_tools.py:96-102`.
  2. Refactor memory extraction to clearly document its deterministic preference rules:
     - Check for keyword patterns (`"manager"`, `"1-on-1"`, `"focus"`, `"lunch"`).
     - Store structured preference keys (`"preferred_meeting_duration"`, `"focus_time_preference"`).
     - Guard against inserting duplicate identical memories.
- **Input / Output Contract:** Predictable, clean memory entries saved to `memory` table upon plan commit.
- **Edge Cases:** Plan with no text or explanation (defaults cleanly without error).
- **What NOT to Do:** Do not introduce external NLP dependencies or async network calls.
- **Verification Commands:**
  ```powershell
  python -m pytest tests/test_plans.py -k "memory"
  ```
- **Definition of Done:** Stored memory keys are well-defined, clean, and tested.
- **Rollback Action:** `git checkout server/tools/commit_tools.py`.

---

### TASK-111: Export OpenAPI Schema & Freeze Backend Contract [GATE-2]
- **Owner:** Codex
- **Priority:** P0 (Integration Gate)
- **Effort Estimate:** 0.5 hours
- **Linked Findings:** Contract Boundary
- **Gate:** **GATE-2 (CONTRACT-FREEZE)**
- **Preconditions:** TASK-101 through TASK-110 completed and verified. Pytest suite 100% pass.
- **Exclusive Edit Scope:** `generated/openapi.json`.
- **Read-Only Scope:** `server/export_openapi.py`, `server/main.py`.
- **Implementation Steps:**
  1. Run `python server/export_openapi.py`.
  2. Confirm `generated/openapi.json` is generated and contains updated schemas (including `lengthened` diff items).
  3. Validate JSON formatting and ensure no breaking changes to existing endpoints.
  4. Publish handoff report to `handoff/` signaling **CONTRACT-FREEZE**.
- **Input / Output Contract:** Fresh, valid OpenAPI 3.1.0 specification committed to `generated/openapi.json`.
- **Edge Cases:** None.
- **What NOT to Do:** Do not edit frontend files.
- **Verification Commands:**
  ```powershell
  python server/export_openapi.py
  git status
  ```
- **Definition of Done:** `generated/openapi.json` is updated and matches active FastAPI routes. Codex execution stops here.
- **Rollback Action:** `git checkout generated/openapi.json`.

---

## 3. Canonical Task Specifications (Gemini Tasks)

---

### TASK-201: Generate Frontend Types from Frozen Schema
- **Owner:** Gemini
- **Priority:** P0 (Type Safety)
- **Effort Estimate:** 0.5 hours
- **Gate:** GATE-3
- **Preconditions:** TASK-111 completed and GATE-2 reached. `generated/openapi.json` exists and is frozen.
- **Exclusive Edit Scope:** `frontend/src/api/types.ts`.
- **Read-Only Scope:** `generated/openapi.json`, `frontend/package.json`.
- **Implementation Steps:**
  1. Run the official type generation script:
     ```powershell
     npm --prefix frontend run typegen
     ```
  2. Inspect `frontend/src/api/types.ts` to verify generated TypeScript types match backend schemas.
  3. Ensure `DiffSummary` types in frontend include the new `lengthened` array:
     ```typescript
     lengthened?: { block_id?: string; title: string; old_duration_min?: number; new_duration_min?: number }[];
     ```
- **Input / Output Contract:** Strongly typed API interfaces matching backend models.
- **Edge Cases:** Schema type mismatches.
- **What NOT to Do:** Do not manually edit backend files or modify `generated/openapi.json`.
- **Verification Commands:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Definition of Done:** `frontend/src/api/types.ts` compiles with `tsc --noEmit` with zero errors.
- **Rollback Action:** `git checkout frontend/src/api/types.ts`.

---

### TASK-202: Render Lengthened Duration Badges in PlanPreview
- **Owner:** Gemini
- **Priority:** P1 (Diff Completeness)
- **Effort Estimate:** 1.0 hour
- **Linked Findings:** FLAW-005
- **Gate:** GATE-3
- **Preconditions:** TASK-201 completed.
- **Exclusive Edit Scope:** `frontend/src/components/PlanPreview.tsx`, `frontend/src/components/PlanPreview.css`.
- **Read-Only Scope:** `frontend/src/App.tsx`.
- **Implementation Steps:**
  1. In `PlanPreview.tsx`, add `DiffItemLengthened` interface and update `DiffSummary`:
     ```typescript
     export interface DiffItemLengthened extends DiffItemKept {
       old_duration_min?: number;
       new_duration_min?: number;
     }
     ```
  2. In JSX render tree, add section for Lengthened blocks:
     ```tsx
     {diff.lengthened && diff.lengthened.length > 0 && (
       <div className="plan-preview-group lengthened">
         <div className="plan-preview-badge lengthened-badge">Lengthened</div>
         <ul>
           {diff.lengthened.map((item, idx) => (
             <li key={idx}>
               <strong>{item.title}</strong>: {item.old_duration_min}m → {item.new_duration_min}m
             </li>
           ))}
         </ul>
       </div>
     )}
     ```
  3. In `PlanPreview.css`, style `.lengthened-badge` with a distinct, pleasant cyan/teal tone matching the palette.
- **Input / Output Contract:** Visually distinct badge and description for extended tasks.
- **Edge Cases:** Diff with 0 lengthened items (section hidden cleanly).
- **What NOT to Do:** Do not alter existing Kept, Moved, Shortened, Dropped, Added styling.
- **Verification Commands:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Definition of Done:** `PlanPreview` renders extended tasks cleanly with duration before/after text.
- **Rollback Action:** `git checkout frontend/src/components/PlanPreview.tsx frontend/src/components/PlanPreview.css`.

---

### TASK-203: Stale-State and Double-Approve Defense in UI
- **Owner:** Gemini
- **Priority:** P0 (UX Robustness)
- **Effort Estimate:** 1.0 hour
- **Linked Findings:** NEW-002
- **Gate:** GATE-3
- **Preconditions:** TASK-201 completed.
- **Exclusive Edit Scope:** `frontend/src/App.tsx`.
- **Read-Only Scope:** `frontend/src/components/PlanPreview.tsx`.
- **Implementation Steps:**
  1. Inspect `frontend/src/App.tsx:163-181` (`handleConfirmPlan`) and `handleCancelPlan`.
  2. Implement local submission lock (`submittingPlanId`):
     - Immediately disable both Confirm and Cancel buttons on first click.
     - Close the proposal modal immediately to prevent repeat clicks.
  3. Catch HTTP 409 errors specifically:
     - If `failure` contains `"STALE_PLAN"` or `"STALE_STATE_VERSION"`, display a friendly toast/banner:
       *"Schedule was updated by another action. Please ask FlowPilot to refresh your plan."*
     - Clear `activePlan` so the stale modal does not trap the user.
- **Input / Output Contract:** Double-clicks on Confirm button are debounced; stale plan errors guide user gracefully.
- **Edge Cases:** Network timeout during confirmation; rapid spam clicking.
- **What NOT to Do:** Do not swallow real 500 errors.
- **Verification Commands:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Definition of Done:** Rapid clicks produce exactly 1 API call; 409 response shows helpful guidance instead of raw error.
- **Rollback Action:** `git checkout frontend/src/App.tsx`.

---

### TASK-204: Alexa+ Ambient Feedback & Interaction Polish
- **Owner:** Gemini
- **Priority:** P1 (Competition Presentation)
- **Effort Estimate:** 1.5 hours
- **Gate:** GATE-3
- **Preconditions:** TASK-203 completed.
- **Exclusive Edit Scope:** `frontend/src/components/UtteranceBar.tsx`, `frontend/src/App.tsx`.
- **Read-Only Scope:** `frontend/src/components/ScheduleTimeline.tsx`, `frontend/src/components/TaskList.tsx`.
- **Implementation Steps:**
  1. Enhance `UtteranceBar.tsx` with quick-prompt chips for the target demo turns:
     - Chip 1: *"Plan my day"*
     - Chip 2: *"Emergency: client sync from 2:00 PM to 3:00 PM"*
     - Chip 3: *"What tasks are left?"*
  2. Add visual ambient indicator (pulsing listening/processing ring in Alexa+ cyan) when agent is thinking (`loading=true`).
  3. Add clear provider indicator (`"Alexa+ Ambient Agent (Gemini 2.5 Flash)"` vs `"Alexa+ Fallback Mode (Deterministic)"`).
- **Input / Output Contract:** Polished ambient interface with 1-click test utterance chips.
- **Edge Cases:** Mobile / narrow screen responsiveness.
- **What NOT to Do:** Do not use copyrighted Alexa logos or trademarks outside permitted hackathon guidelines.
- **Verification Commands:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Definition of Done:** Quick chips populate input bar; processing animation triggers during turn; UI feels responsive and premium.
- **Rollback Action:** `git checkout frontend/src/components/UtteranceBar.tsx frontend/src/App.tsx`.

---

### TASK-205: Accessibility & Keyboard Navigation Hardening
- **Owner:** Gemini
- **Priority:** P1 (A11y & Compliance)
- **Effort Estimate:** 1.0 hour
- **Gate:** GATE-3
- **Preconditions:** TASK-202, TASK-204 completed.
- **Exclusive Edit Scope:** `frontend/src/components/PlanPreview.tsx`, `frontend/src/components/TaskList.tsx`.
- **Read-Only Scope:** `frontend/src/App.tsx`.
- **Implementation Steps:**
  1. Add `aria-live="polite"` to agent response announcements and status banners.
  2. Ensure modal dialogs (`PlanPreview`) trap focus and allow `Escape` key dismissal.
  3. Ensure contrast ratios on diff badges exceed WCAG AA standards (4.5:1).
  4. Ensure all interactive buttons have explicit `aria-label` attributes.
- **Input / Output Contract:** Accessible DOM tree navigable via Tab, Enter, and Escape.
- **Edge Cases:** Screen readers announcing rapid state updates.
- **What NOT to Do:** Do not break existing CSS layout or overflow behavior.
- **Verification Commands:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Definition of Done:** PlanPreview dialog is dismissible with Escape key; screen readers announce new proposals.
- **Rollback Action:** `git checkout frontend/src/components/PlanPreview.tsx frontend/src/components/TaskList.tsx`.

---

## 4. Integration, Verification, and Submission Tasks (Integrator & Human)

---

### TASK-301: Full Clean-Clone & Golden Smoke Test Gate Execution
- **Owner:** Integrator / Human
- **Priority:** P0 (Release Gate)
- **Effort Estimate:** 1.0 hour
- **Gate:** **GATE-4 (CODE-FREEZE)**
- **Preconditions:** All Codex tasks (101–111) and Gemini tasks (201–205) completed.
- **Exclusive Edit Scope:** `docs/hackathon-release/` (reporting logs only).
- **Read-Only Scope:** Full repository.
- **Implementation Steps:**
  1. Execute clean-clone smoke validation in PowerShell:
     ```powershell
     powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
     ```
  2. Execute full backend test suite:
     ```powershell
     python -m pytest tests/
     ```
  3. Execute frontend production build:
     ```powershell
     npm --prefix frontend run build
     ```
  4. Verify git status is clean and tag release candidate:
     ```powershell
     git status
     git tag v1.0.0-rc1
     ```
- **Definition of Done:** Zero test failures, clean production bundle, zero uncommitted files, release tag created.
- **Rollback Action:** Address failing test before tagging.

---

### TASK-302: Record & Validate 3-Minute Demo Video Walkthrough
- **Owner:** Human
- **Priority:** P0 (Submission Mandatory)
- **Effort Estimate:** 2.0 hours
- **Gate:** **GATE-5 (SUBMISSION)**
- **Preconditions:** TASK-301 passed. Application running via `scripts/dev.ps1`.
- **Implementation Steps:**
  1. Prepare clean browser window at 1920x1080 resolution.
  2. Reset session to fresh state (`handleReset` or click Reset).
  3. Record video adhering to the 3-minute shot list in `docs/hackathon-release/06_DEVPOST_SUBMISSION_KIT.md`:
     - **0:00–0:25:** Hook & Problem (calendar thrash, emergency interruptions).
     - **0:25–1:15:** Turn 1 (Day planning, focus tasks, immutable meetings, diff review, human confirm).
     - **1:15–2:00:** Turn 2 (Emergency client sync at 2 PM, gap-jumping, overflow buffer absorption, confirm).
     - **2:00–2:20:** Turn 3 (Remaining tasks query, offline fallback demonstration).
     - **2:20–2:30:** Closing summary & architectural highlights.
  4. Upload to YouTube as Unlisted/Public, verify 1080p playback and audio clarity.
- **Definition of Done:** Public/Unlisted YouTube link under 3:00 (target 2:30) demonstrating genuine working software.

---

### TASK-303: Final Devpost Package & Track Verification
- **Owner:** Human
- **Priority:** P0 (Submission Mandatory)
- **Effort Estimate:** 1.5 hours
- **Gate:** **GATE-5 (SUBMISSION)**
- **Preconditions:** TASK-302 video link available.
- **Implementation Steps:**
  1. Populate Devpost submission form using verified copy from `docs/hackathon-release/06_DEVPOST_SUBMISSION_KIT.md`.
  2. Confirm track selection: **Alexa+** (Simulated Web Experience).
  3. Confirm claims register: Do NOT claim AWS Builder or genuine hardware Alexa.
  4. Paste public GitHub repo link and verify Apache-2.0 license is recognized.
  5. Submit before the T-2h target buffer (`2026-10-23 22:30 IST`).
- **Definition of Done:** Devpost submission confirmation received and archived.
