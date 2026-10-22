# FlowPilot Hackathon Release Contract — Scope, Invariants, Deadlines, and Gates

> **Purpose:** Authoritative release contract defining hackathon goals, non-negotiable invariants, time budgets, minimum shippable scope, explicit out-of-scope boundaries, and go/no-go milestone gates.  
> **Last verified against commit:** `f2f2706`  
> **Status Legend:**  
> - `[VERIFIED]`: Confirmed directly in active repository source code, git history, or live environment.  
> - `[INFERRED]`: Reasoned from configuration and hackathon rules; pending execution.  
> - `[NOT RUN]`: Explicitly unexecuted in the current session.  
> - `[PROPOSED]`: Architecture recommendation subject to human release manager approval.  

---

## 1. Executive Release Goal & Track Alignment

FlowPilot is an ambient AI scheduling assistant built for knowledge workers facing fluid, high-interruption workdays. It acts as an intelligent executive assistant that schedules tasks around protected commitments, handles mid-day emergency meetings gracefully, and never modifies a user's calendar without explicit human approval.

### 1.1 Target Competition & Track
- **Competition:** *Build, Ship, Shape: Amazon Developer Hackathon 2026*
- **Primary Track:** **Alexa+**  
- **Track Vehicle:** Simulated Alexa+ Web Experience (`frontend/` React 19 + TypeScript SPA communicating with `server/` FastAPI backend).
- **Rule Verification:** Hackathon rules explicitly permit a simulated Alexa+ web interface showcasing conversational ambient planning, voice/text intent understanding, and multimodal card feedback. Genuine Alexa Skills Kit (`ask-sdk`) or Alexa Voice Service (`AVS`) hardware integration is **NOT** present in the codebase and is **NOT** claimed.

---

## 2. Protected Architecture Invariants

The following invariants are hard constraints. Any commit, refactor, or suggestion that violates these invariants must be rejected immediately:

1. **Strict Tier Separation (`READ -> PROPOSE -> Human Review -> COMMIT`):**
   - The LLM agent loop operates strictly within the `READ` and `PROPOSE` tiers.
   - The LLM **NEVER** has access to `COMMIT` tools (`commit_schedule`). Code inspection of `server/providers/gemini.py:36, 98-100` proves that `commit_schedule` is excluded from LLM function declarations and rejected at runtime if attempted.
   - Proposals are staged in `plans` table with `status='PROPOSED'`. They do not mutate `calendar_blocks` or `tasks` until confirmed.
2. **Explicit Human Confirmation Boundary:**
   - Calendar blocks mutate if and only if a human user executes an explicit HTTP `POST /api/v1/sessions/{sid}/plans/{pid}/confirm` action via the UI.
3. **Atomic & Rollback-Safe Commits:**
   - Commit operations in `server/tools/commit_tools.py` execute inside a SQLite transaction (`SAVEPOINT commit_domain` / `BEGIN IMMEDIATE`).
   - If any step fails (e.g. block overlap, foreign key error, unhandled exception), the entire operation rolls back, leaving database state identical to pre-commit.
4. **Optimistic Concurrency & Stale State Protection:**
   - Every proposal records `state_version_at_proposal`.
   - The confirm endpoint rejects any proposal whose version does not match the active `sessions.state_version` with HTTP `409 Conflict` (`STALE_PLAN`).
5. **Explainable Before/After Diffs:**
   - Every proposal computes a structured 5-way differential (`kept`, `moved`, `shortened`, `dropped`, `added`, plus `lengthened` post-remediation) via `server/engine/differ.py`.
   - The UI presents this diff visually before the user decides to confirm or cancel.
6. **Immutable Block Preservation:**
   - Protected blocks (`immutable=1` or `status='completed'`) such as "Team Standup", "Lunch", or past meetings cannot be moved, shortened, or dropped by any automated proposal (`server/engine/validator.py:45-59`).

---

## 3. Deadline, Time Remaining, and Proposed Buffers

### 3.1 Clocks and Remaining Window
- **Current Environment Time:** `2026-10-22T02:43:14+05:30` (IST) `[VERIFIED]`
- **Official Submission Deadline:** `2026-10-24T00:30:00+05:30` (October 24, 2026, 12:30 AM IST) `[VERIFIED]`
- **Total Time Remaining:** **45 hours, 46 minutes, 46 seconds** (~45.78 hours).

### 3.2 Milestone Timeline and Proposed Safety Buffers
*(All buffer targets marked [PROPOSED, human may change]):*

| Milestone / Gate | Target Timestamp (IST) | Countdown from Start | Buffer to Hard Deadline | Focus |
|---|---|---|---|---|
| **Gate 0: Preflight & Baseline Audit** | `2026-10-22 04:00 IST` | T+1h 17m | 44h 30m remaining | Clean-clone baseline, audit completion, task board lock |
| **Gate 1: Backend Algorithm Hardening** | `2026-10-22 18:00 IST` | T+15h 17m | 30h 30m remaining | FLAW-001, 002, 003, 005, 006, 007 fixed by Codex; pytest pass |
| **Gate 2: CONTRACT-FREEZE** | `2026-10-22 21:00 IST` | T+18h 17m | 27h 30m remaining | OpenAPI schema exported, frontend types generated, API locked |
| **Gate 3: Frontend UX & Diff Polish** | `2026-10-23 09:00 IST` | T+30h 17m | 15h 30m remaining | Gemini completes diff badges, task list, error handling, a11y |
| **Feature Freeze [PROPOSED]** | `2026-10-23 12:00 IST` | T+33h 17m | **12h 30m remaining** | No new features; only bug fixes, docs, and demo rehearsal |
| **Gate 4: Golden Smoke & E2E Validation**| `2026-10-23 15:00 IST` | T+36h 17m | 9h 30m remaining | Clean-clone smoke script passes 100% on fresh database |
| **Code Freeze & Demo Cut [PROPOSED]** | `2026-10-23 18:00 IST` | T+39h 17m | **6h 30m remaining** | Repository locked (`v1.0.0-rc1`); demo video recorded (< 3 min) |
| **Final Submission Target [PROPOSED]**| `2026-10-23 22:30 IST` | T+43h 47m | **2h 00m safety buffer**| Devpost form completed, YouTube unlisted/public verified |
| **HARD SUBMISSION DEADLINE** | `2026-10-24 00:30 IST` | T+45h 47m | **0h 00m** | Submission portal closes |

---

## 4. Minimum Shippable Scope (MVS)

The Minimum Shippable Scope guarantees an impressive, compliant, and rock-solid submission even if non-essential polish tasks are cut:

1. **Functional Web Application:**
   - Single-process or dual-process local execution (`npm run dev` / `scripts/dev.ps1`).
   - Clean, reactive UI with real-time schedule timeline, active task board, utterance bar, diff preview modal, and tool trace inspection drawer.
2. **Deterministic & Live Agent Demo Journey:**
   - **Turn 1 (Initial Planning):** User says *"Plan my day"* -> Agent reads 4 pending tasks + 2 calendar blocks, schedules focus and regular tasks into available slots, presents clear diff -> User reviews and clicks **Confirm** -> Database commits atomically.
   - **Turn 2 (Emergency Interruption):** User says *"Emergency: client sync from 2:00 PM to 3:00 PM"* -> Agent preserves protected morning blocks and lunch, slots the meeting, shifts afternoon focus work into the 4:00 PM overflow buffer without collision or crash -> User reviews explainable diff (interruption added, focus moved, buffer shortened) and clicks **Confirm**.
   - **Turn 3 (Task Status Inspection):** User says *"What tasks are left?"* -> Agent returns structured, readable list of remaining pending tasks with deadlines.
3. **Resilient Offline / Fallback Capability:**
   - If `GEMINI_API_KEY` is absent or the live API trips the circuit breaker (2 errors), the system falls back seamlessly to `DeterministicProvider` with `degraded=True` indicator. No crashes, no blank screens.
4. **Reproducible Local Setup:**
   - Verified step-by-step instructions in `README.md` working from a fresh git clone in Windows PowerShell.
5. **Open Source & Submission Artifacts:**
   - Apache-2.0 License in repo root.
   - Public GitHub repository without secrets or temporary build artifacts.
   - 2.5-minute public video walkthrough hosted on YouTube with clear audio and captions.
   - Devpost description explaining architecture, problem solved, and technical friction logs.

---

## 5. Explicit Out-of-Scope List (Do Not Attempt)

To prevent deadline failure and scope creep, the following areas are strictly **OUT OF SCOPE**:

1. **Hardware Alexa / AVS Integration:** No integration with Amazon Echo devices, smart speakers, or Alexa Voice Service. Track entry relies strictly on the permitted simulated Alexa+ web interface.
2. **Native AWS Cloud Infrastructure Deployment:** No AWS Lambda packaging, CDK scripts, ECS Fargate clusters, or API Gateway setups unless a verified 1-click script exists. Local deployment is the canonical test target.
3. **Multi-Day / Overnight Scheduling (FLAW-012):** Midnight-crossing shifts or multi-day planning are out of scope. The scheduler operates strictly on the 09:00–17:00 single-day boundary. Documented as a known domain constraint.
4. **Natural Language Memory & Sentiment Inference (FLAW-004):** No open-ended LLM memory extraction pipeline. Preference storage is restricted to deterministic, keyword-safe preference tracking.
5. **External Calendar Sync:** No Google Calendar OAuth2, Microsoft Graph, or Apple CalDAV integrations. Calendar persistence is strictly local SQLite.
6. **Multi-Tenant User Management & Auth:** No JWT user authentication, passwords, or signup flows. Sessions are ephemeral UUID-based sandbox instances.

---

## 6. Critical Go/No-Go Milestone Gates

A gate is passed only when all criteria are met and verified by an exact PowerShell command:

- **GATE 0: Baseline Verification**
  - Criteria: `git status` clean; `python -m pytest tests/` passes; `npm --prefix frontend run build` passes.
  - Decision: **GO** (Verified in preflight).
- **GATE 1: Core Algorithmic & Persistence Hardening (Codex)**
  - Criteria: FLAW-001 (focus slicing), FLAW-002 (greedy placement), FLAW-003 (replan crash), FLAW-005 (differ gap), and FLAW-006 (block UUID mutation) resolved; zero pytest regressions.
  - Decision: **Codex Stop Point** -> Handoff to Gate 2.
- **GATE 2: CONTRACT-FREEZE (Codex -> Gemini Handoff)**
  - Criteria: `python server/export_openapi.py` outputs valid `generated/openapi.json`; `npm --prefix frontend run typegen` updates `frontend/src/api/types.ts`; zero git diff between backend schema and client types.
  - Decision: **LOCK API**. Gemini is unblocked for frontend tasks. Backend endpoints cannot change without human approval.
- **GATE 3: UI & Alexa+ Experience Polish (Gemini)**
  - Criteria: PlanPreview renders all diff badges (including lengthened); double-confirm prevented; task list renders cleanly; ARIA labels and keyboard navigation functional.
  - Decision: **Gemini Stop Point** -> Handoff to Gate 4.
- **GATE 4: Golden Smoke & Clean-Clone Verification**
  - Criteria: `scripts/smoke.ps1` executes successfully end-to-end on a freshly initialized database without LLM errors.
  - Decision: **CODE FREEZE**. Branch tagged `v1.0.0-rc1`.
- **GATE 5: Submission Release Gate (Human)**
  - Criteria: Video recorded (< 3 min, 1080p); Devpost draft submitted; GitHub repo public; license verified.
  - Decision: **FINAL SHIP**.

---

## 7. Judge-Access Decision & Hosting Strategy

- **Primary Evaluation Path [Human-confirm]:** **Local Run + Video Walkthrough.**  
  Judges evaluate FlowPilot by cloning the repository, running `scripts/dev.ps1` (or `npm run dev`), and following the 3-minute scripted test scenario documented in `README.md`. A pristine 1080p YouTube video demonstrates the exact same flow.
- **Secondary / Optional Hosted URL Path [Human-confirm: PROPOSED P2]:**  
  Because the hackathon track permits local simulation and video demonstration, public cloud hosting is **NOT** a disqualifying requirement. However, `server/main.py:58-60` is already wired to serve `frontend/dist` as static files. If desired, a containerized or single-process deployment to a platform such as Render or Railway can be executed as a P2 task *only after* Gate 4 is passed. No external deployment credentials or accounts are assumed.
