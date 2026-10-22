# FlowPilot Codex Execution Plan — Backend, Engine, and Persistence Hardening

> **Purpose:** Detailed implementation guide for OpenAI Codex (backend and reliability lead) mapping 1:1 to canonical tasks TASK-101 through TASK-111. Contains unit tests to create, exact file boundaries, failure modes, checkpoint verification commands, commit conventions, and the contract freeze procedure.  
> **Last verified against commit:** `f2f2706`  
> **Status Legend:**  
> - `[VERIFIED]`: Confirmed directly in active repository source code, git history, or live environment.  
> - `[INFERRED]`: Reasoned from configuration and hackathon rules; pending execution.  
> - `[NOT RUN]`: Explicitly unexecuted in the current session.  
> - `[P0]`: Critical priority — required for shippable MVS and demo integrity.  
> - `[P1]`: High priority — completeness, polish, and error prevention.  
> - `[P2]`: Normal priority — secondary optimization or enhancement.  

---

## 1. Operating Rules for Codex Executor

1. **Strict 1:1 Mapping:** Execute tasks strictly by stable ID in the order listed below. Do not invent new tasks or renumber existing ones. Full task specifications reside in `docs/hackathon-release/02_ORDERED_TASK_GRAPH.md`.
2. **Batch Size Limit:** Work in small, focused batches (1 to 3 tasks maximum). Run unit tests after each task.
3. **Commit Convention:** Every git commit must reference the task ID in its header:
   - Format: `feat(TASK-xxx): <imperative summary>` or `fix(TASK-xxx): <imperative summary>`.
4. **Clean Handoff Report:** When completing a task or hitting a gate, write a short summary conforming to §4 before continuing.
5. **No Secret Access:** Never read, echo, or commit `.env` or credential files.
6. **Exclusive Scope:** Touch ONLY backend files (`server/`, `tests/`, `generated/openapi.json`). Never edit frontend files (`frontend/`).

---

## 2. Ordered Codex Implementation Specifications

---

### [TASK-101] Fix Replan Collision with Immutable Blocks (FLAW-003)
- **Specification Reference:** See [TASK-101 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-101-fix-replan-collision-with-immutable-blocks).
- **Target File:** `server/engine/scheduler.py` (`compute_replan`).
- **Tests to Add (`tests/test_engine.py`):**
  - `test_replan_jumps_over_immutable_meeting()`: Setup day with 12:00 Lunch and 15:30 Client Sync. Inject 14:00–15:00 interruption. Verify displaced afternoon task is scheduled into the 16:00 overflow slot without raising `ValueError("Replan collides with immutable block")`.
  - `test_replan_preserves_immutable_meeting_identity()`: Confirm that `Team standup` and `Lunch` maintain identical start and end times.
- **Boundaries & Invariants:**
  - Immutable blocks (`immutable=True` or `status='completed'`) must NEVER move or shrink.
  - Total day duration cannot exceed 17:00:00.
- **Failure Modes:** Overlapping blocks; moving immutable blocks; infinite loop when finding next free slot.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_engine.py tests/test_propose.py -v
  ```
- **Commit Message:** `fix(TASK-101): implement gap-jumping for replanning around immutable meetings`

---

### [TASK-102] Flexible Focus & Task Duration Fitting (FLAW-001)
- **Specification Reference:** See [TASK-102 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-102-flexible-focus--task-duration-fitting).
- **Target File:** `server/engine/scheduler.py` (`compute_day_schedule`).
- **Tests to Add (`tests/test_engine.py`):**
  - `test_focus_task_larger_than_160_minutes()`: Pass a 180-minute focus task. Verify it splits dynamically across available morning/afternoon gaps instead of throwing `ValueError("Focus task exceeds available reservations")`.
  - `test_personal_task_full_duration_preserved()`: Pass a 60-minute personal errand. Verify it receives 60 minutes on the calendar rather than being truncated to 45 minutes.
- **Boundaries & Invariants:**
  - High-priority tasks take precedence over medium and low priority.
  - Tasks with explicit deadlines must finish before `task['deadline']`.
- **Failure Modes:** Scheduling past 17:00:00; tasks violating deadlines.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_engine.py -k "focus or personal" -v
  ```
- **Commit Message:** `fix(TASK-102): remove hardcoded focus slicing and personal duration truncation`

---

### [TASK-103] Multi-Pass Free Interval Gap Placement (FLAW-002)
- **Specification Reference:** See [TASK-103 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-103-multi-pass-free-interval-gap-placement).
- **Target File:** `server/engine/scheduler.py` (`place` helper).
- **Tests to Add (`tests/test_engine.py`):**
  - `test_gap_placement_with_dense_preexisting_blocks()`: Create schedule with 5 staggered calendar commitments. Schedule 3 tasks. Verify all placed blocks strictly satisfy pairwise non-overlap (`validate_schedule` returns zero errors).
- **Boundaries & Invariants:** Pairwise non-overlap invariant strictly enforced.
- **Failure Modes:** $O(N^2)$ excessive looping; failure to detect small free windows.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_engine.py tests/test_golden_smoke.py -v
  ```
- **Commit Message:** `feat(TASK-103): replace greedy single-pass placement with multi-pass gap interval fitting`

---

### [TASK-104] Lengthened Duration Classification in Differ (FLAW-005)
- **Specification Reference:** See [TASK-104 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-104-lengthened-duration-classification-in-differ).
- **Target File:** `server/engine/differ.py` (`compute_diff`).
- **Tests to Add (`tests/test_engine.py`):**
  - `test_diff_detects_lengthened_block()`: Create old block 09:00–09:30 (30m). Propose new block 09:00–10:30 (90m). Verify `diff["lengthened"]` contains block title with `old_duration_min=30, new_duration_min=90`.
  - Verify block does not appear in `kept` or `shortened`.
- **Boundaries & Invariants:** Wire format must maintain backward compatibility: `kept`, `moved`, `shortened`, `dropped`, `added` remain present.
- **Failure Modes:** Block classified simultaneously as kept and lengthened.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_engine.py -k "test_diff" -v
  ```
- **Commit Message:** `feat(TASK-104): classify extended block durations in schedule diff output`

---

### [TASK-105] Preserve Block UUIDs & Enforce Atomic Commit (FLAW-006, NEW-001)
- **Specification Reference:** See [TASK-105 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-105-preserve-block-uuids--enforce-atomic-commit).
- **Target File:** `server/tools/commit_tools.py` (`commit_schedule`).
- **Tests to Add (`tests/test_plans.py`):**
  - `test_commit_preserves_persistent_meeting_uuids()`: Create session with seed blocks. Propose day schedule without explicit IDs. Commit schedule. Verify `Team standup` row in `calendar_blocks` has the exact same `id` UUID as before commit.
  - `test_atomic_rollback_on_partial_commit_failure()`: Mock an exception during task status update. Verify `calendar_blocks` and `tasks` tables roll back to pre-commit state.
- **Boundaries & Invariants:** Foreign key integrity (`ON DELETE CASCADE`) preserved.
- **Failure Modes:** Stray orphaned calendar blocks; missing task updates.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_plans.py tests/test_idempotency.py -v
  ```
- **Commit Message:** `fix(TASK-105): preserve calendar block UUIDs on LLM proposals and enforce atomic commit rollback`

---

### [TASK-106] Inbound State Version Validation & Rate Eviction (FLAW-007, FLAW-009)
- **Specification Reference:** See [TASK-106 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-106-inbound-state-version-validation--rate-eviction).
- **Target File:** `server/routers/agent.py` (`agent_message`).
- **Tests to Add (`tests/test_agent_loop.py`):**
  - `test_agent_message_rejects_stale_state_version()`: Submit message with `state_version: 0` when session is at version 1. Verify HTTP 409 response with error code `STALE_STATE_VERSION`.
  - `test_agent_message_accepts_current_or_none_state_version()`: Submit with matching version or `None`. Verify HTTP 200.
- **Boundaries & Invariants:** Optional field: requests omitting `state_version` must still succeed.
- **Failure Modes:** Rejecting valid requests; breaking initial session turns.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_agent_loop.py tests/test_stale_plan.py -v
  ```
- **Commit Message:** `feat(TASK-106): validate inbound client state version in agent message route`

---

### [TASK-107] Proposal Garbage Collection in Database (FLAW-008)
- **Specification Reference:** See [TASK-107 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-107-proposal-garbage-collection-in-database).
- **Target File:** `server/tools/propose_tools.py` (`_propose_impl`).
- **Tests to Add (`tests/test_propose.py`):**
  - `test_propose_cancels_superseded_proposals()`: Call `propose_schedule` twice in a row. Verify in database that plan #1 has `status='CANCELLED'` and plan #2 has `status='PROPOSED'`.
- **Boundaries & Invariants:** Never cancel plans with status `'CONFIRMED'`, `'EXECUTED'`, or `'FAILED'`.
- **Failure Modes:** Cancelling active executed plans.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_propose.py -v
  ```
- **Commit Message:** `fix(TASK-107): supersede abandoned proposals in database upon new proposal creation`

---

### [TASK-108] Scoped Tool Repair in Gemini Provider Loop (FLAW-011)
- **Specification Reference:** See [TASK-108 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-108-scoped-tool-repair-in-gemini-provider-loop).
- **Target File:** `server/providers/gemini.py` (`_run`).
- **Tests to Add (`tests/test_gemini_provider.py`):**
  - `test_multi_tool_repair_recovers_gracefully()`: Simulate a turn where tool #1 requires schema repair, and tool #2 also requires argument repair. Verify both recover without throwing an unhandled exception.
- **Boundaries & Invariants:** Turn limit (16 rounds) remains strictly bounded.
- **Failure Modes:** Infinite repair cycles consuming user LLM quota.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_gemini_provider.py -k "test_repair" -v
  ```
- **Commit Message:** `fix(TASK-108): scope tool argument repairs per call to allow multi-step recovery`

---

### [TASK-109] Database Secondary Indexes for Foreign Keys (FLAW-010)
- **Specification Reference:** See [TASK-109 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-109-database-secondary-indexes-for-foreign-keys).
- **Target File:** `server/database.py` (`SCHEMA`).
- **Tests to Add (`tests/test_scaffolding.py`):**
  - `test_database_schema_has_secondary_indexes()`: Query `sqlite_master` for indexes on `calendar_blocks`, `tasks`, and `plans`. Verify indexes exist.
- **Boundaries & Invariants:** Idempotent schema initialization (`CREATE INDEX IF NOT EXISTS`).
- **Failure Modes:** Syntax error in SQLite DDL.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_scaffolding.py -v
  ```
- **Commit Message:** `perf(TASK-109): add SQLite secondary indexes on session foreign keys`

---

### [TASK-110] Deterministic Preference Matching Cleanup (FLAW-004)
- **Specification Reference:** See [TASK-110 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-110-deterministic-preference-matching-cleanup).
- **Target File:** `server/tools/commit_tools.py` (`_update_memory`).
- **Tests to Add (`tests/test_plans.py`):**
  - `test_deterministic_preference_extraction()`: Verify clean key-value insertion into `memory` table upon plan commit.
- **Boundaries & Invariants:** Deterministic; zero external network requests.
- **Failure Modes:** Duplicate memory bloat.
- **Checkpoint Command:**
  ```powershell
  python -m pytest tests/test_plans.py -k "memory" -v
  ```
- **Commit Message:** `refactor(TASK-110): sanitize deterministic preference extraction and storage`

---

### [TASK-111] Export OpenAPI Schema & Freeze Backend Contract [GATE-2]
- **Specification Reference:** See [TASK-111 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-111-export-openapi-schema--freeze-backend-contract-gate-2).
- **Target File:** `generated/openapi.json`.
- **Preconditions:** All preceding Codex tasks (TASK-101 through TASK-110) must be completed and passing. Full pytest suite must pass with 0 errors.
- **Execution Instructions:**
  1. Run the contract export script:
     ```powershell
     python server/export_openapi.py
     ```
  2. Run the full pytest suite to verify zero regressions:
     ```powershell
     python -m pytest tests/ -v
     ```
  3. Inspect `git status` to verify `generated/openapi.json` is updated.
  4. Commit the frozen schema:
     ```powershell
     git add generated/openapi.json
     git commit -m "chore(TASK-111): export openapi schema and freeze backend API contract"
     ```
  5. **STOP EXECUTION.** Publish Handoff Report per §4. Codex work is complete. Gemini is unblocked.

---

## 3. Codex Checkpoint Commands Summary

```powershell
# Run after every scheduler task (TASK-101, 102, 103):
python -m pytest tests/test_engine.py tests/test_propose.py -v

# Run after differ task (TASK-104):
python -m pytest tests/test_engine.py -k "test_diff" -v

# Run after persistence & commit tasks (TASK-105, 107, 109, 110):
python -m pytest tests/test_plans.py tests/test_idempotency.py tests/test_scaffolding.py -v

# Run after router & provider tasks (TASK-106, 108):
python -m pytest tests/test_agent_loop.py tests/test_gemini_provider.py -v

# Final Gate 1 & Gate 2 verification (must pass 100%):
python -m pytest tests/ -v
python server/export_openapi.py
```

---

## 4. Codex Handoff Report Format

Upon reaching **GATE-2 (CONTRACT-FREEZE)**, Codex must produce a handoff report in the following format:

```markdown
### Codex Backend Execution Summary
- **Completed Tasks:** TASK-101, TASK-102, TASK-103, TASK-104, TASK-105, TASK-106, TASK-107, TASK-108, TASK-109, TASK-110, TASK-111
- **Current Git Commit:** <git rev-parse --short HEAD>
- **Git Diff Stat:** <git diff --stat HEAD~N>
- **Pytest Results:** <total passed> passed, 0 failed, 1 deselected in <time>s
- **OpenAPI Schema Status:** Exported to `generated/openapi.json` and verified
- **Gate Status:** GATE-1 PASSED, GATE-2 (CONTRACT-FREEZE) REACHED
- **Next Action:** Gemini executor starts TASK-201
```
