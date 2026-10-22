# FlowPilot Codebase — Comprehensive Technical Mechanism & Flaws Audit

**Target System:** FlowPilot Ambient AI Scheduling Agent  
**Context:** Amazon Developer Hackathon 2026 (Alexa+ Track)  
**Document Classification:** Deep Technical Architecture, Mechanism Breakdown, and Architectural Flaws Audit  
**Date:** 2026-10-22  

---

## 1. Executive System Topology & Data Flow

FlowPilot operates as a deterministic, human-in-the-loop ambient scheduling platform. The core invariant of the system is **Tier Separation**:
1. **READ**: Queries persistent session data without mutating state.
2. **PROPOSE**: Computes prospective schedules, runs invariant validations, generates structured diffs, and writes temporary draft plans (`status='PROPOSED'`).
3. **COMMIT**: Requires explicit human confirmation to apply changes atomically to committed calendar tables and advance the session `state_version`.

```
[ User Utterance ]
        │
        ▼
[ /sessions/{sid}/agent/message ] ── (Rate Limiting: 10/min)
        │
        ▼
[ Provider Router ] ────────────────────────┐
   ├── DeterministicProvider (Regex/Offline)│
   └── FallbackProvider ────────────────────┤
         ├── Primary: GeminiProvider (Live) │
         └── Circuit Breaker (2 fail -> 60s)│
                                            │
                                            ▼
                               [ Function Calling Loop ]
                                            │
        ┌───────────────────────────────────┼────────────────────────────────────┐
        ▼                                   ▼                                    ▼
[ READ Tools ]                     [ PROPOSE Tools ]                     [ COMMIT Tools ]
- get_tasks                         - propose_schedule                   - commit_schedule
- get_calendar                      - propose_replan                     (Blocked from LLM;
- get_schedule                              │                            executed strictly via
- get_current_time                          ▼                            POST /plans/{pid}/confirm)
- get_memory                       [ Scheduler Engine ]
                                            │
                                            ▼
                                   [ Validator Engine ]
                                            │
                                            ▼
                                     [ Differ Engine ]
                                            │
                                            ▼
                                  [ Draft in `plans` ]
                                            │
        ┌───────────────────────────────────┘
        ▼
[ JSON Response ] ──> [ Frontend App.tsx ] ──> [ PlanPreview Modal ] ──> [ User Confirms ]
```

---

## 2. Component-by-Component Mechanism Breakdown

### 2.1 Database & Persistence Layer (`server/database.py`)
- **Engine**: SQLite with WAL mode (`PRAGMA journal_mode = WAL`), foreign keys enabled (`PRAGMA foreign_keys = ON`), and a 5-second busy timeout (`PRAGMA busy_timeout = 5000`).
- **Schema**:
  - `sessions`: Tracks `id`, `state_version` (integer counter for optimistic concurrency), `demo_timestamp` (virtual clock override), and `provider`.
  - `tasks`: Unscheduled to-dos. Enforces strict `CHECK` constraints on `priority IN ('HIGH','MEDIUM','LOW')`, `category IN ('work','personal','meeting')`, and `status IN ('pending','scheduled','completed','cancelled')`.
  - `calendar_blocks`: Committed calendar entries. Tracks `start_time`, `end_time`, `immutable` (boolean flag protecting meetings/lunch), `status` (`scheduled`, `completed`), and `task_id` (foreign key to `tasks.id`).
  - `plans`: Draft schedules created by `propose_*`. Tracks `status` (`PROPOSED`, `CONFIRMED`, `EXECUTING`, `EXECUTED`, `FAILED`, `CANCELLED`, `STALE`), `proposed_blocks` (serialized JSON), `diff_summary` (serialized JSON), and `state_version_at_proposal`.
  - `execution_log`: Append-only audit trail logging tool name, serialized arguments, serialized result, and execution duration.
  - `memory`: Key-value pair storage for preference entries.
- **Connection Model**: Per-request connection lifecycle (`get_connection()` ... `connection.close()`).

### 2.2 Time & Clock Virtualization (`server/clock.py`)
- **Mechanism**: The `now()` function accepts an optional `demo_timestamp`.
  - If `demo_timestamp` is supplied, it parses the ISO string, validates timezone awareness, and freezes or offsets time to that timestamp.
  - If `None`, it falls back to `datetime.now(timezone.utc)`.
- **Purpose**: Enables repeatable, deterministic evaluations and golden demo walkthroughs regardless of local system wall-clock time.

### 2.3 Algorithmic Scheduler Engine (`server/engine/scheduler.py`)

#### A. Initial Schedule Generation (`compute_day_schedule`)
- **Inputs**: `tasks`, `calendar_blocks`, `current_time`.
- **Logic**:
  1. Sets origin to `09:00:00` of current day and `day_end` to `17:00:00` (strictly 8 hours).
  2. Filters tasks for non-assigned, non-completed items, sorting them by Priority (`HIGH=0`, `MEDIUM=1`, `LOW=2`) and then by `deadline`.
  3. Inserts a fixed 5-minute `"Planning"` reservation at `09:00–09:05`.
  4. Identifies the primary `"focus"` task (`category == 'work'` and `duration_minutes > 60`):
     - Slices the focus task into up to three rigid time chunks: `(offset=5m, len=55m)` [09:05–10:00], `(offset=135m, len=60m)` [11:15–12:15], and `(offset=300m, len=45m)` [14:00–14:45].
  5. Schedules other tasks using hardcoded initial offset targets:
     - Personal + Low priority -> offset `360m` (15:00).
     - Personal + High/Medium -> offset `195m` (12:15), capped at 45 minutes duration.
     - Other tasks -> offset `90m` (10:30).
  6. Inserts a `"Buffer / overflow"` block at offset `420m` (16:00–17:00).
  7. Runs `validate_schedule`.

#### B. Dynamic Replanning (`compute_replan`)
- **Inputs**: `current_blocks`, `interruption`, `current_time`.
- **Logic**:
  1. Marks any calendar block whose `end_time <= now` as `completed` and `immutable=True`.
  2. Drops completed `"Planning"` blocks.
  3. Verifies that the `interruption` interval is in the future and does not overlap any in-progress or immutable blocks.
  4. Scans blocks starting after the interruption:
     - Sets a shifting `cursor = interruption.end_time`.
     - Non-immutable blocks are shifted forward: `shifted = max(left, cursor)`.
     - When the `"Buffer / overflow"` block is encountered, it is compressed: `finish = right` (keeping its original end time), absorbing the delay and shortening the buffer.
     - If shifting pushes a block past an immutable block, it raises an error.

### 2.4 Schedule Validation Engine (`server/engine/validator.py`)
- **Checks Executed**:
  1. `start_time` must strictly precede `end_time`.
  2. Both `start_time` and `end_time` must fall within the current calendar day (`start.date() == now.date()`).
  3. Overlap check: Pairwise $O(N^2)$ interval intersection test (`start < other_end and other_start < end`).
  4. Protected Block Invariance: Every existing block marked `immutable=True` or `status='completed'` MUST exist in the new schedule with identical `start_time`, `end_time`, and `title`.

### 2.5 Difference Engine (`server/engine/differ.py`)
- **Mechanism**: Computes a 5-way differential between `old_blocks` and `new_blocks`:
  - `kept`: Block start and end times are unchanged.
  - `moved`: Start time has changed.
  - `shortened`: New duration is strictly less than old duration.
  - `dropped`: Block present in `old_blocks` is missing from `new_blocks`.
  - `added`: Block present in `new_blocks` was not in `old_blocks`.
- **Identity Resolution**: Resolves block identity by persistent ID first, falling back to matching by `title` or `task_id`.

### 2.6 Tool Registry & Permissions (`server/tools/`)
- Tools are declared with strict JSON Schema definitions (`additionalProperties: False`).
- **Tier Invariant**:
  - `READ`: `get_tasks`, `get_calendar`, `get_current_time`, `get_schedule`, `get_memory`.
  - `PROPOSE`: `propose_schedule`, `propose_replan`.
  - `COMMIT`: `commit_schedule`.
- **Safety Gate**: The LLM agent loop strictly filters available tools to `READ` and `PROPOSE`. The model has **no execution access** to `commit_schedule`.

### 2.7 Providers & Execution Loop (`server/providers/`)
- **`DeterministicProvider`**: Pure offline provider. Uses regex pattern matching on the message (`plan`, `replan`, `left/remaining`) to invoke pre-wired tool sequences without network calls or LLM inference.
- **`GeminiProvider`**: Uses Google GenAI SDK (`google-genai`).
  - Feeds conversation history and declarations into a maximum 16-step tool execution loop.
  - Single-attempt repair mechanism: If a tool argument fails validation, returns a repair instruction to the model once.
- **`FallbackProvider`**: Implements circuit-breaker pattern:
  - If `GeminiProvider` throws 2 consecutive errors, trips the circuit for 60 seconds, routing all requests to `DeterministicProvider` with `degraded=True`.

### 2.8 Plan Confirmation & Commit Engine (`server/tools/commit_tools.py`)
- **Atomicity**: Wrapped in a SQLite transaction (`BEGIN IMMEDIATE` and `SAVEPOINT commit_domain`).
- **Optimistic Locking**: Compares `plan.state_version_at_proposal` against `session.state_version`. If they do not match, marks the plan `STALE` and rejects with HTTP 409.
- **Execution**:
  1. Updates plan status `PROPOSED -> CONFIRMED -> EXECUTING`.
  2. Upserts blocks in `calendar_blocks` table.
  3. Deletes removed non-completed blocks.
  4. Updates associated task statuses to `'scheduled'`.
  5. Keyword-based memory generation.
  6. Increments `session.state_version`.
  7. Updates plan status to `EXECUTED`.

### 2.9 Frontend Architecture (`frontend/src/`)
- Single-page React application built with TypeScript and Vite.
- Maintains local state for `sid`, `stateVersion`, `blocks`, `tasks`, `activePlan`, `agentResponse`, and `toolTrace`.
- **Components**:
  - `UtteranceBar`: Text input with submission debouncing.
  - `ResponseLine`: Smart parser rendering assistant responses as interactive task cards when lists/tasks are detected.
  - `PlanPreview`: Visual diff modal rendering Kept, Moved, Shortened, Dropped, and Added badges with Confirm and Cancel buttons.
  - `ScheduleTimeline`: Chronological visual block timeline with live time indicators.
  - `TaskList`: Dedicated tabbed task board displaying priorities, durations, deadlines, and one-click scheduling triggers.

---

## 3. Comprehensive Audit of Logical Flaws & Hidden Limitations

The following table documents the **12 verified architectural limitations, logic flaws, and fragility points** present in the codebase:

| Flaw ID | Component | Severity | Category | Description |
|---|---|---|---|---|
| **FLAW-001** | `scheduler.py` | HIGH | Hardcoded Logic | Rigid Focus Slicing (55/60/45) & Personal Truncation |
| **FLAW-002** | `scheduler.py` | HIGH | Algorithmic Fragility | Single-Pass Greedy Slot Placement Fails on Dense Blocks |
| **FLAW-003** | `scheduler.py` | CRITICAL | Fault Intolerance | Replan Immediately Fails on Immutable Collision Instead of Resolving |
| **FLAW-004** | `commit_tools.py` | MEDIUM | Synthetic Architecture | Hardcoded Keyword Matching for Memory Extraction |
| **FLAW-005** | `differ.py` | MEDIUM | Diff Classification Gap | Lengthened Duration Disappears from Diff Output |
| **FLAW-006** | `commit_tools.py` | MEDIUM | Data Identity Mutation | Persistent UUID Regeneration for LLM-Proposed Blocks |
| **FLAW-007** | `agent.py` | MEDIUM | Concurrency Gap | Request `state_version` is Accepted but Ignored in `agent_message` |
| **FLAW-008** | `propose_tools.py` | LOW | Resource Leak | Unconfirmed Proposals Are Orphaned in Database Indefinitely |
| **FLAW-009** | `agent.py` | MEDIUM | Ephemeral State | In-Memory Sliding Window Rate Limiter Resets on Process Restart |
| **FLAW-010** | `database.py` | MEDIUM | Performance / Scalability | Complete Absence of Secondary Database Indexes on Foreign Keys |
| **FLAW-011** | `gemini.py` | HIGH | Error Recovery Limit | Turn-Global `repaired` Boolean Prevents Multi-Step Tool Recovery |
| **FLAW-012** | `validator.py` | LOW | Domain Constraint | Strict Same-Day Constraint Prohibits Midnight-Crossing & Multi-Day Tasks |

---

### Detailed Technical Breakdown of Each Flaw

#### FLAW-001: Rigid Focus Slicing & Task Truncation (`scheduler.py:48-64`)
- **Mechanism**:
  ```python
  focus = next((task for task in pending if task.get("category") == "work" and task["duration_minutes"] > 60), None)
  ...
  for part, (offset, reservation) in enumerate(((5, 55), (135, 60), (300, 45)), 1):
  ```
- **Flaw**:
  1. The focus task slicing is hardcoded specifically to slots of 55 min, 60 min, and 45 min. If a focus task requires more than $55 + 60 + 45 = 160$ minutes (e.g. a 3-hour task), it immediately throws `ValueError("Focus task exceeds available reservations")`.
  2. Personal tasks are arbitrarily truncated to 45 minutes:
     ```python
     duration = min(task["duration_minutes"], 45) if personal and not low else task["duration_minutes"]
     ```
     If the user has a 60-minute gym session or a 90-minute medical appointment, the engine silently shrinks it to 45 minutes without notifying the user or recording the cut!

#### FLAW-002: Single-Pass Greedy Placement Fails on Dense Blocks (`scheduler.py:31-45`)
- **Mechanism**:
  ```python
  def place(title, offset, minutes, task=None):
      start = max(origin + timedelta(minutes=offset), now)
      duration = timedelta(minutes=minutes)
      for block in sorted(blocks, key=lambda item: _time(item["start_time"])):
          left, right = _time(block["start_time"]), _time(block["end_time"])
          if start < right and start + duration > left:
              start = right
  ```
- **Flaw**:
  This is a single-pass greedy scan. When `start = right` pushes `start` into the future, the algorithm does not restart verification against earlier blocks or test whether the new slot overlaps subsequent blocks that were already iterated over. If the list contains complex pre-existing calendar commitments, this algorithm can place overlapping blocks or fail validation.

#### FLAW-003: Replan Rejection on Immutable Collision (`scheduler.py:97-101`)
- **Mechanism**:
  ```python
  if block.get("immutable"):
      if left < cursor:
          raise ValueError("Replan collides with immutable block")
      cursor = right
  ```
- **Flaw**:
  When an interruption occurs (e.g. 2 PM meeting) and pushes preceding tasks forward, if those tasks collide with an immutable meeting later in the day (e.g. a 3:30 PM client call), the replanner does **not** attempt to split tasks, jump over the immutable meeting, or drop lower-priority tasks. It raises an unhandled `ValueError`, causing the agent turn to fail or return a 500 error!

#### FLAW-004: Hardcoded Keyword Matching for Memory Extraction (`commit_tools.py:96-102`)
- **Mechanism**:
  ```python
  text = " ".join([plan["explanation"] or "", *(b["title"] for b in blocks)]).lower()
  manager = "manager" in text or "1-on-1" in text
  key = "manager_meeting" if manager else "work_style"
  value = "Manager 1-on-1 typically 30 min, schedule for unexpected" if manager else "User prefers morning focus blocks for reports"
  ```
- **Flaw**:
  The memory system does not use AI extraction, NLP, or user preferences. It checks whether the string contains `"manager"` or `"1-on-1"`. If true, it saves a hardcoded string about managers; otherwise, it saves a hardcoded string about morning focus blocks. It cannot learn arbitrary user habits.

#### FLAW-005: Lengthened Duration Disappears from Diff Output (`differ.py:19-27`)
- **Mechanism**:
  ```python
  if old["start_time"] == match["start_time"] and old["end_time"] == match["end_time"]:
      result["kept"].append(base)
  if old["start_time"] != match["start_time"]:
      result["moved"].append(...)
  if new_duration < old_duration:
      result["shortened"].append(...)
  ```
- **Flaw**:
  If a block's start time remains identical but its end time is extended (e.g., from 30 minutes to 60 minutes):
  - It is NOT `kept` (since `end_time` changed).
  - It is NOT `moved` (since `start_time` is the same).
  - It is NOT `shortened` (since duration increased).
  - The diff schema has no `lengthened` category.
  The block completely vanishes from the diff summary!

#### FLAW-006: Persistent UUID Regeneration for LLM Blocks (`commit_tools.py:76-95`)
- **Mechanism**:
  ```python
  bid = block.get("id") or str(uuid4())
  old = db.execute("SELECT * FROM calendar_blocks WHERE id=?", (bid,)).fetchone()
  ...
  for row in db.execute("SELECT id FROM calendar_blocks WHERE session_id=? AND status != 'completed'", (sid,)).fetchall():
      if row["id"] not in retained:
          db.execute("DELETE FROM calendar_blocks WHERE id=? AND session_id=?", (row["id"], sid))
  ```
- **Flaw**:
  When Gemini proposes a schedule, it generates blocks conforming to the tool schema without database UUIDs. Because `block.get("id")` is `None`, `commit_tools` generates a brand new `uuid4()` for every block. When pruning blocks not in `retained`, SQLite deletes the existing database rows for `Team standup` and `Lunch` and inserts brand new rows with new UUIDs. While titles and times are preserved, all external entity references or foreign keys referencing the old UUIDs are broken.

#### FLAW-007: Unvalidated `state_version` in Agent Message Endpoint (`routers/agent.py:36-82`)
- **Mechanism**:
  ```python
  class AgentMessageRequest(BaseModel):
      message: str = Field(min_length=1, max_length=1000)
      state_version: int | None = None
  ```
- **Flaw**:
  While `AgentMessageRequest` accepts `state_version`, the route handler never validates it against `sessions.state_version`. If a stale frontend client submits a prompt based on an outdated schedule, the agent processes it without warning. Optimistic concurrency is only checked much later when `/confirm` is called.

#### FLAW-008: Orphaned Proposals in Database (`tools/propose_tools.py:47-54`)
- **Mechanism**:
  Every call to `propose_schedule` or `propose_replan` executes:
  ```python
  INSERT INTO plans (id, session_id, status, proposed_blocks, ...) VALUES (?, ?, 'PROPOSED', ...)
  ```
- **Flaw**:
  If a user prompts the agent three times in a row, three separate rows are created with `status='PROPOSED'`. Only the last plan is confirmed; the earlier proposals remain in the database as orphaned `PROPOSED` rows forever without being expired or marked `CANCELLED`.

#### FLAW-009: In-Memory Rate Limiter Reset on Server Restart (`routers/agent.py:21, 57-65`)
- **Mechanism**:
  ```python
  _message_times: dict[str, deque[float]] = {}
  _rate_lock = Lock()
  ```
- **Flaw**:
  Rate limiting (10 requests/min per session) is stored in an in-memory dictionary.
  1. Any server restart or multi-worker deployment (e.g. Gunicorn/Uvicorn with `--workers 4`) wipes or partitions rate-limiting state.
  2. Expired session keys are never deleted from `_message_times`, causing an unbounded memory leak over long uptime periods.

#### FLAW-010: Missing Secondary Indexes on Foreign Keys (`database.py:11-18`)
- **Mechanism**:
  `SCHEMA` defines primary keys on `id` but zero secondary indexes:
  ```sql
  CREATE TABLE calendar_blocks (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ...);
  CREATE TABLE tasks (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ...);
  CREATE TABLE plans (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ...);
  ```
- **Flaw**:
  Every single read query (`SELECT * FROM calendar_blocks WHERE session_id = ?`, `SELECT * FROM tasks WHERE session_id = ?`) executes a full table scan. In multi-session production databases, performance degrades linearly ($O(N)$) with total rows.

#### FLAW-011: Turn-Global `repaired` Flag Blocks Multi-Step Tool Recovery (`providers/gemini.py:66, 104-106`)
- **Mechanism**:
  ```python
  repaired = False
  for _ in range(16):
      ...
      except (ValidationError, ValueError, KeyError, TypeError) as exc:
          if repaired:
              raise
          repaired = True
          tool_result = {"validation_error": str(exc), "instruction": "Repair the tool arguments once."}
  ```
- **Flaw**:
  `repaired` is a single boolean scoped to the entire 16-turn loop. If tool call #1 has a minor schema typo, it is repaired. If tool call #3 (e.g. `propose_schedule`) subsequently encounters a validation error, `if repaired: raise` immediately aborts the conversation turn and crashes the request instead of giving the model a chance to repair the schedule.

#### FLAW-012: Strict Same-Day Constraint (`validator.py:34-35`)
- **Mechanism**:
  ```python
  if now is not None and (start.date() != now.date() or end.date() != now.date()):
      errors.append(f"Block {index}: outside current day bounds")
  ```
- **Flaw**:
  Tasks that cross midnight (e.g. night shifts from 23:00 to 02:00) or multi-day planning are rejected by the validator as malformed. The entire application is architecturally constrained to single-day schedules between 00:00 and 23:59.

---

## 4. Architectural Hardening Recommendations

1. **Scheduler Generalization**:
   - Replace rigid chunking `(55, 60, 45)` with dynamic interval fitting: calculate free slot gaps between immutable blocks and greedily fit tasks by priority.
   - On replan collision with immutable blocks, introduce gap-jumping (schedule remaining work after the immutable block) rather than throwing `ValueError`.
2. **Schema & Indexing Hardening**:
   - Add secondary indexes:
     ```sql
     CREATE INDEX IF NOT EXISTS idx_calendar_blocks_session ON calendar_blocks(session_id, start_time);
     CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id, status);
     CREATE INDEX IF NOT EXISTS idx_plans_session ON plans(session_id, status);
     ```
3. **Diff Classifier Completion**:
   - Add a `lengthened` category to `compute_diff` to represent blocks whose duration increases without changing `start_time`.
4. **Resilient Tool Repair**:
   - Scope `repaired` per tool call or per round rather than per turn.
5. **Proposal Garbage Collection**:
   - When a new plan is proposed in `propose_tools.py`, automatically mark any existing `PROPOSED` plans for that session as `CANCELLED` or `SUPERSEDED`.
