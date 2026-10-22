# FlowPilot Agent Coordination, Protocols, and Exact Prompts

> **Purpose:** Multi-agent operational playbook, strict file ownership boundaries, branching policies, handoff protocols, and exact copy-paste prompts for Codex, Gemini, and the Independent Verifier.  
> **Last verified against commit:** `f2f2706`  
> **Status Legend:**  
> - `[VERIFIED]`: Confirmed directly in active repository source code, git history, or live environment.  
> - `[INFERRED]`: Reasoned from configuration and hackathon rules; pending execution.  
> - `[NOT RUN]`: Explicitly unexecuted in the current session.  
> - `[LOCKED]`: Exclusive file boundary assigned to a single agent.  

---

## 1. Strict File Ownership Matrix

To prevent git merge conflicts, state corruption, and race conditions, **no file may ever be edited by more than one agent**. Shared configuration files are locked to Human approval:

| File / Directory Path | Exclusive Write Owner | Read-Only Access | Purpose & Scope |
|---|---|---|---|
| `server/engine/scheduler.py` | **Codex** `[LOCKED]` | Gemini, Human | Scheduling algorithms, focus slicing, replanning, gap-jumping |
| `server/engine/differ.py` | **Codex** `[LOCKED]` | Gemini, Human | Wire diff classification (kept, moved, shortened, lengthened) |
| **`server/engine/validator.py`** | **FROZEN** (Human only) | Codex, Gemini | Invariant validator (preserves protected meetings and intervals) |
| `server/tools/commit_tools.py` | **Codex** `[LOCKED]` | Gemini, Human | Atomic commit transactions, UUID preservation, preference matching |
| `server/tools/propose_tools.py` | **Codex** `[LOCKED]` | Gemini, Human | Proposal generation, proposal cancellation / cleanup |
| `server/routers/agent.py` | **Codex** `[LOCKED]` | Gemini, Human | Agent message endpoint, inbound state version validation |
| `server/providers/gemini.py` | **Codex** `[LOCKED]` | Gemini, Human | Provider loop, tool repair scoping, retry budgets |
| `server/database.py` | **Codex** `[LOCKED]` | Gemini, Human | SQLite schema, connection lifecycle, secondary indexes |
| `generated/openapi.json` | **Codex** (to Gate 2) | Gemini, Human | Exported OpenAPI 3.1 specification (locked at CONTRACT-FREEZE) |
| `tests/*.py` | **Codex** `[LOCKED]` | Gemini, Human | Unit and integration test suites |
| `frontend/src/api/types.ts` | **Gemini** `[LOCKED]` | Codex, Human | TypeScript API client types generated from frozen schema |
| `frontend/src/components/PlanPreview.*` | **Gemini** `[LOCKED]` | Codex, Human | Diff modal, lengthened badge rendering, modal keyboard trap |
| `frontend/src/App.tsx` | **Gemini** `[LOCKED]` | Codex, Human | React root, double-confirm defense, stale state handling |
| `frontend/src/components/UtteranceBar.*` | **Gemini** `[LOCKED]` | Codex, Human | Utterance bar, demo prompt chips, ambient pulse glow |
| `frontend/src/components/TaskList.*` | **Gemini** `[LOCKED]` | Codex, Human | Task board view, accessibility attributes, list styling |
| `frontend/src/components/*.css` | **Gemini** `[LOCKED]` | Codex, Human | Visual styling, badge themes, high-contrast accessible tokens |
| `package.json`, `requirements.txt` | **Human** `[LOCKED]` | Codex, Gemini | Core dependencies (dependency additions require human approval) |
| `README.md`, `LICENSE` | **Human** `[LOCKED]` | Codex, Gemini | Repo overview, run instructions, license metadata |
| `docs/hackathon-release/*.md` | **Integrator / Human** | Codex, Gemini | Release contract, audit, task graph, and gate reports |

---

## 2. Sequencing, Branching, and Gate Handshake Policy

```
[ Gate 0: Baseline Verified ]
            │
            ▼
[ Codex Execution: TASK-101 .. TASK-110 ] ── (Backend Algorithms & Invariants)
            │
            ▼
[ Gate 2: CONTRACT-FREEZE (TASK-111) ] ───── (OpenAPI Schema Frozen in generated/openapi.json)
            │
            ▼
[ Gemini Execution: TASK-201 .. TASK-205 ] ─ (Frontend Types, Diff Modal, A11y, UX)
            │
            ▼
[ Gate 4: Clean-Clone Smoke (TASK-301) ] ─── (Tag v1.0.0-rc1, Lock Code)
            │
            ▼
[ Gate 5: Video & Devpost (TASK-302, 303) ] ─ (Public Submission Complete)
```

### 2.1 Branch and Tag Conventions
- All work executes directly on `main` using short-lived commit milestones.
- Checkpoint tags:
  - `v1.0.0-rc1`: Created at **GATE-4** upon full passing of `scripts/smoke.ps1` and `pytest`.
  - `v1.0.0-final`: Created at **GATE-5** upon Devpost submission confirmation.

### 2.2 Conflict Resolution & Rollback Policy
- If an agent task causes unit test regressions or build errors that cannot be repaired within 30 minutes, the agent must immediately execute the documented rollback command (`git checkout <file>`) and log the blocker in its handoff report.
- Never use `git reset --hard` or destructive git commands.

---

## 3. Standard Agent Handoff Report Template

Every executor (Codex or Gemini) must conclude each work batch with this exact Markdown report structure:

```markdown
### Agent Execution Handoff Report
- **Agent Role:** [Codex Backend Lead | Gemini Frontend Lead | Integrator]
- **Completed Tasks:** [e.g. TASK-101, TASK-102]
- **Active Git Commit:** [e.g. 7f2a1b4]
- **Files Modified (`git diff --stat`):**
  [Paste output of git diff --stat]
- **Verification Commands Executed & Results:**
  - Command: `python -m pytest tests/test_engine.py` -> Passed: 14, Failed: 0
  - Command: `npm --prefix frontend run build` -> Passed (235ms)
- **API / Contract Modifications:** [None | Documented changes to generated/openapi.json]
- **Encountered Blockers / Deviations:** [None | Description of issue]
- **Next Milestone Gate:** [GATE-1 | GATE-2 | GATE-3 | GATE-4]
- **Allowed Claims Status:** [Confirmed unchanged per claims register]
```

---

## 4. Exact Copy-Paste Executor Prompts

Use the following exact prompts in Cursor or your agent environment. Each prompt instructs the model to read local specifications, execute only 1–3 tasks, test rigorously, and halt at its gate:

---

### Prompt A: Codex Backend Lead (Start Batch 1)

```text
You are Codex, Principal Backend & Reliability Engineer for FlowPilot.
Operating Environment: Windows / PowerShell / Cursor.
Use your most capable model configuration.

READ ONLY the following planning files before writing code:
- docs/hackathon-release/00_RELEASE_CONTRACT.md (invariants and deadlines)
- docs/hackathon-release/02_ORDERED_TASK_GRAPH.md (specifications for TASK-101, TASK-102, TASK-103)
- docs/hackathon-release/03_CODEX_EXECUTION.md (Codex test requirements and commands)

MISSION: Execute Batch 1 of Backend Hardening:
1. TASK-101: Fix replan collision with immutable blocks (server/engine/scheduler.py)
2. TASK-102: Flexible focus and duration allocation without truncation (server/engine/scheduler.py)
3. TASK-103: Multi-pass free interval gap placement (server/engine/scheduler.py)

STRICT BOUNDARIES:
- Exclusive edit scope: server/engine/scheduler.py and tests/test_engine.py.
- Do NOT edit frontend files or package.json.
- Do NOT touch or view secrets or .env files.
- Add unit tests for each task as specified in 03_CODEX_EXECUTION.md.
- Run checkpoint command:
  python -m pytest tests/test_engine.py tests/test_propose.py -v

When tests pass with 0 failures, commit changes using convention:
  feat(TASK-101): implement gap-jumping for replan around immutable blocks
  feat(TASK-102): dynamic focus and duration allocation
  feat(TASK-103): multi-pass interval gap placement

Then STOP and output the Standard Agent Handoff Report defined in docs/hackathon-release/07_AGENT_COORDINATION_AND_PROMPTS.md §3.
```

---

### Prompt B: Codex Backend Lead (Batch 2 to CONTRACT-FREEZE)

```text
You are Codex, Principal Backend & Reliability Engineer for FlowPilot.
Operating Environment: Windows / PowerShell / Cursor.

READ ONLY the following planning files before writing code:
- docs/hackathon-release/02_ORDERED_TASK_GRAPH.md (TASK-104 through TASK-111)
- docs/hackathon-release/03_CODEX_EXECUTION.md (test details and commands)

MISSION: Complete Batch 2 and freeze the backend contract at GATE-2:
1. TASK-104: Lengthened duration classification in differ (server/engine/differ.py)
2. TASK-105: Preserve block UUIDs and enforce atomic commit (server/tools/commit_tools.py)
3. TASK-106: Inbound state version validation (server/routers/agent.py)
4. TASK-107: Proposal garbage collection in database (server/tools/propose_tools.py)
5. TASK-108: Scoped tool repair in Gemini provider loop (server/providers/gemini.py)
6. TASK-109: Secondary database indexes for foreign keys (server/database.py)
7. TASK-110: Deterministic preference matching cleanup (server/tools/commit_tools.py)
8. TASK-111: Export OpenAPI schema and reach GATE-2 (generated/openapi.json)

VERIFICATION COMMANDS:
  python -m pytest tests/ -v
  python server/export_openapi.py

When all tests pass and openapi.json is exported, commit:
  chore(TASK-111): export openapi schema and freeze backend API contract

STOP and output the Handoff Report confirming GATE-2 (CONTRACT-FREEZE) has been reached.
```

---

### Prompt C: Gemini Frontend Lead (GATE-2 to GATE-3)

```text
You are Gemini, Principal Frontend, UX, and Product Lead for FlowPilot.
Operating Environment: Windows / PowerShell / Cursor.

PREREQUISITE CHECK:
Confirm that generated/openapi.json exists and Codex has confirmed GATE-2 (CONTRACT-FREEZE).

READ ONLY the following planning files:
- docs/hackathon-release/00_RELEASE_CONTRACT.md (MVS scope and UI states)
- docs/hackathon-release/02_ORDERED_TASK_GRAPH.md (TASK-201 through TASK-205)
- docs/hackathon-release/04_GEMINI_EXECUTION.md (frozen API contracts and component specs)

MISSION: Implement Frontend Polish & Alexa+ Ambient Experience:
1. TASK-201: Sync frontend types from frozen schema:
   npm --prefix frontend run typegen
2. TASK-202: Render Lengthened duration badges in PlanPreview modal (PlanPreview.tsx, PlanPreview.css)
3. TASK-203: Stale-state (409) and double-approve race defense in App.tsx
4. TASK-204: Alexa+ ambient glow, mode badge, and quick demo chips (UtteranceBar.tsx, App.tsx)
5. TASK-205: Accessibility and keyboard navigation (PlanPreview.tsx, TaskList.tsx)

STRICT BOUNDARIES:
- Touch ONLY frontend/src/ components and styles.
- Do NOT edit backend Python files.
- Do NOT read or commit secrets.

VERIFICATION COMMANDS:
  npm --prefix frontend run build

When the build passes cleanly with 0 TypeScript errors, commit:
  feat(TASK-201-205): complete frontend diff badges, stale defense, and Alexa+ ambient UI

STOP and output the Standard Agent Handoff Report confirming GATE-3 has been reached.
```

---

### Prompt D: Final Integrator & Smoke Verifier (GATE-4)

```text
You are the Independent Release Verifier and Integration Lead for FlowPilot.
Operating Environment: Windows / PowerShell.

READ ONLY:
- docs/hackathon-release/05_TEST_AND_RELEASE_GATES.md (clean-clone smoke and scenario tables)
- docs/hackathon-release/06_DEVPOST_SUBMISSION_KIT.md (claims register and video timeline)

MISSION: Execute Gate 4 Verification on the complete application:
1. Verify git working tree is clean:
   git status
2. Execute full backend test harness:
   python -m pytest tests/ -v
3. Execute frontend production build:
   npm --prefix frontend run build
4. Run automated smoke script:
   powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
5. Tag release candidate:
   git tag v1.0.0-rc1

Verify that:
- Zero tests fail.
- Build completes cleanly.
- Commit hash is recorded.
- No uncommitted files or secrets exist.

Output the final verification summary confirming readiness for video recording (TASK-302) and Devpost submission (TASK-303).
```
