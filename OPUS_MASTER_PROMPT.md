# Opus One-Shot Architecture Handoff Prompt

Prepared by Claude · October 21, 2026 · Paste-ready prompt for Claude Opus 4.6 Thinking in Antigravity IDE

## Mission: One-Shot Architecture Handoff

**Build, Ship, Shape: Amazon Developer Hackathon 2026, Alexa+ Track, solo.**

You are a Principal Product Architect, Hackathon Strategist, Tech Lead and Multi-Agent Workflow Designer, running in the root of a new repository in Antigravity IDE. **This is the only planned Opus session.** Quota is scarce. Your output is a set of files on disk that lets three executors build and submit the project without you:

- **Gemini Flash (Antigravity)** is the Coordinator. It reads the docs, tracks state, does light tasks, delegates heavy tasks, and independently verifies everything.
- **OpenAI Codex** is the Heavy Executor. It does one scoped implementation task at a time.
- **Human (solo)** is the Product Owner. They handle keys, manual QA, screen recording and the Devpost submission.

### Session rules

- Do not ask questions. Do not write feature code. Do not print file contents in chat. Create files with IDE tools and verify them.
- Be decisive. Never leave “option X or Y” in a spec; lock decisions in as law.
- Only state capabilities (tools, SDK versions, agent integrations, quotas, rule details) you have verified in this workspace. When something cannot be verified now, choose the safest assumption. Then add a concrete verification task **and** a fully specified fallback branch in the docs. This is a legitimate planned branch, not an unresolved question.
- Do not output a reasoning transcript. Keep the final chat message short.

## 1. Fixed facts (inputs, not for debate)

- **Deadline:** Oct 23, 2026 12:00 PM PDT = Oct 24, 2026 12:30 AM IST. Verify the conversion in the shell. Express human-facing schedules in IST and also give T-minus anchors.
- **Track:** Alexa+. Two permitted approaches:
  - **A:** a working Agent Skill or self-hosted MCP server implementing MCP spec `2025-11-25` or later over Streamable HTTP.
  - **B:** a simulated Alexa+ experience built with any AI or agentic tools. No Alexa hardware or production Alexa+ backend is needed. Source code must be included, and the demo must clearly show the simulated experience working.
  - Never claim access to production Alexa+ services.
- **Stage 1 gate:** fits Alexa+, uses a permitted approach legitimately, is runnable, and is demonstrated in a video under 3 minutes.
- **Stage 2:** four equal pillars at 25% each: Tech Implementation (real execution, protocol coherence, reliability, multi-step state), Design (a complete product, not a dev console or ChatGPT clone, with explicit confirmation UX), Potential Impact (a visceral, relatable pain point clear in the first 15 seconds), and Quality of Idea (not a single-turn chatbot or API wrapper).
- **Mandatory submission deliverables (all P0):**
  - source repo accessible to judges
  - public demo video under 180s (plan for ≤170s)
  - testing instructions
  - product feedback
  - English everywhere

  The official rules text may not be in the workspace. Check, and if it is absent, create a Human P0 task to verify these against the Devpost page, including whether a hosted URL is required.
- **Optional bonuses:**
  - The Friction Log bonus (up to +10%) is worth low-effort continuous logging.
  - The AWS Builder mini-challenge defaults to SKIP, because promotional credits are exhausted and nothing may need paid AWS. A P2 isolated adapter is allowed only if it costs nothing and cannot touch P0.
  - The Open Source mini-challenge is SKIP.
  - Optional scope must never delay or endanger a submission requirement.
- **Environment:** Windows, no Docker or Kubernetes, near-zero budget (GitHub Student Pack, Azure for Students, free Gemini/OpenAI tiers), solo human.
- **Golden rule:** a finishable, demo-reliable product beats a complex, broken one.

## 2. Step 0: inspect before deciding

Using the shell, record only what you verify:

- current date, time and timezone
- the workspace listing and `git status` (run `git init` and an initial commit if needed)
- shell type (PowerShell version)
- versions of python, node, npm and git
- whether a Codex CLI exists
- any rules or notes files in the repo

Compute **R** (the remaining hours to deadline) from the clock. If the clock is unreadable, plan with T-minus anchors only and say so. Select a scope profile:

- **R ≥ 36h:** Full profile.
- **20h ≤ R < 36h:** Reduced profile. P1 limited to polish that is cheap and safe.
- **R < 20h:** Minimal profile. Vertical slice plus the golden demo on the deterministic provider, plus submission tasks.

Size P0 so it completes by about 45% of R. Size P1 to finish by the freeze. Reserve the rest for slack, rehearsal and submission.

## 3. Decisions to make (record briefly in `docs/09_DECISIONS.md`)

**3.1 Concept tournament.** Evaluate three finalists:

1. **Deadline Rescue / FlowPilot with a signature feature, Interrupt-and-Recover Planning.** The agent builds a concrete time-block schedule from messy tasks and constraints and commits it after approval. When an interruption arrives (a meeting moves, time shrinks, a task overruns), it replans the remaining schedule. Completed blocks stay immutable. It shows a diff (kept, moved, shortened, dropped), explains trade-offs against priorities and deadlines, and commits atomically after approval.
2. and 3. Two genuinely different Alexa+-appropriate concepts you design: no hardware, real stateful multi-step tool use, human approval for consequential actions, a visual surface, and cross-session memory.

Score each 1–5 on the four pillars, then apply pass/fail gates. A candidate that fails any gate is eliminated regardless of score:

- P0 buildable within the runway profile.
- Reliably demoable in under 3 minutes.
- Real stateful tool execution, not CRUD plus generated text.
- Clearly not a chatbot or to-do app.

Do not default to Candidate 1. Whatever wins must include an equivalent mid-flow interrupt-and-replan capability that preserves prior state. Give the winner a product name. Put the compact matrix in ADR-001.

**3.2 Track approach.** Evaluate A (MCP only), B (simulation only) and C (hybrid) on:

- eligibility clarity
- coherence with the judging pillars
- the real hours cost of a correct MCP implementation (Streamable HTTP, JSON-RPC lifecycle, protocol version and session headers, Origin validation and localhost binding)
- demo risk
- honesty

Do not assume hybrid is best. The rules below hold regardless of which approach you pick:

- If the eligibility path includes an MCP server, it is P0 and needs a conformance task (for example the official MCP Inspector, if available). It must expose the same single tool registry the app uses, not a second implementation.
- Use the official SDK only if its `2025-11-25` conformance is verified. Otherwise use a fully specified minimal handler.
- If B is the basis, MCP is optional P1. The registry’s tool schemas must still be MCP-shaped (`name`, `description`, `inputSchema`) at no extra cost.
- The README, the video and the Devpost text must state exactly what is simulated and what is real MCP.

**3.3 Stack.** Choose ONE stack. Decide using these criteria:

- runtimes actually installed (§2)
- reliability for Gemini Flash and Codex
- transactional SQLite on Windows
- a contract-drift prevention mechanism
- avoiding native-module build risk on Windows (prefer stdlib or prebuilt binaries)
- single-process, single-origin serving

If a required runtime is missing, add a Human P0 install task. Pin versions only if verified. Otherwise require the lockfile to record the resolved versions.

**3.4 Remaining ADRs.**

- ADR-004: provider strategy (§4.5).
- ADR-005: AWS Builder and Open Source disposition.
- A dated section that Gemini appends to for runtime decisions.

## 4. Architecture requirements

Everything below is specified exactly **once**, in `docs/02_ARCHITECTURE.md`, which is the single authoritative contract. All other documents reference it by section and never restate it.

**4.1 Contract contents.**

- Component boundaries.
- The configuration and environment variable table. `.env.example` must mirror it, with clearly labelled fake example values.
- SQLite tables: columns, types, constraints, indexes. Every table is session-scoped.
- The tool registry, one table with: `name`, `tier` (READ, PROPOSE or COMMIT), JSON Schema parameters, return shape, side effects, and validation rules.
- Every REST endpoint with exact JSON request and response shapes, one error envelope, and `state_version`.
- The plan state machine with idempotent transitions (PROPOSED → CONFIRMED → EXECUTING → EXECUTED | FAILED | CANCELLED | STALE).
- A sequence diagram of the agent loop, including the interrupt and replan flow.
- The UI-visible tool trace, sourced from the persisted execution log.

**4.2 Contract integrity mechanism.**

- Generate the machine-readable schema (OpenAPI) from the backend models, plus frontend types from it. Or use an equally simple single-source mechanism that fits your stack.
- Provide ONE command, `contract:check`, that fails on drift between committed generated artifacts and fresh generation.
- The frontend may use only generated types.
- Backend tests validate responses against the schema.
- Deviation process:
  - **Class A (additive, backward-compatible).** Gemini may edit 02 first, then code, in the same commit, and log the change.
  - **Class B (rename, remove, type change, table change, tool change, state-machine change).** Gemini updates 02 and every dependent task in one commit, runs `contract:check`, and logs an ADR. It may not change P0 scope, the track approach or the golden demo; those need the Human, plus an optional Opus audit.

**4.3 Design rule: the LLM proposes, code disposes.**

- Scheduling, conflict detection and diffing are deterministic, validated code inside tools.
- The LLM only chooses tools and arguments and writes the explanation.
- Planning may call only READ and PROPOSE tools, which mutate nothing.
- COMMIT tools run only via the confirm endpoint on a stored, validated plan. A plan’s confirmation is set by the human HTTP action, never by model output.
- If MCP is exposed, it exposes READ and PROPOSE tools. Any commit works only for plans already human-approved.

**4.4 The clock.** The clock is injectable. The golden demo uses a fixed demo timestamp, so recordings and tests are reproducible at any real time.

**4.5 Provider strategy (three distinct things).**

1. **Live LLM** (`gemini` required to be supported; `openai` P2 or optional). Live is optional for initial development.
2. **Deterministic provider** (`deterministic`, the default). It is a rule-based provider that runs real tools against real DB state for the seeded scenario. The UI must always show a mode badge (“Live model” or “Deterministic demo mode”). It is never presented as autonomous reasoning.
3. **Offline fixtures.** Recorded or handwritten provider responses used only by the test harness, with no network.

Policies:

- A single live-call timeout, with at most one retry on 5xx or timeout.
- No retry on 429.
- One repair attempt for malformed tool arguments (feed back the validation error).
- After that, fall back to deterministic with an explicit `degraded: true` and `provider_used` field and a visible notice.
- A circuit breaker skips live calls for 60s after two consecutive failures.
- Specify the timeout values and the latency budgets in §4.7.

**4.6 Security model (simple, hackathon-appropriate).**

- API keys live only in backend env. `.env` is gitignored. The browser never sees keys.
- No real personal data. Demo data is fictional. Logs never contain keys.
- SQLite: foreign keys on, WAL, busy timeout, and one transaction per commit. A commit is all-or-nothing, with rollback on any step failure and an execution log recording the outcome.
- Idempotent confirm: an atomic status transition guard. A repeated confirm returns the stored result without re-executing.
- Stale-plan protection: confirm is rejected with 409 if `state_version` changed since the plan was proposed.
- Pydantic or equivalent input validation, with length limits and enums.
- A tool allowlist and schema validation of all LLM tool calls. IDs must belong to the caller’s session. The model never supplies the session ID.
- Server-generated opaque session tokens and strict per-session data isolation.
- Prompt injection: stored user content is delimited as untrusted data in prompts. Include a seeded injection note in the test fixtures and a test proving it has no effect.
- A session-scoped reset only. There is no global wipe endpoint; a full wipe is a CLI script. Reset is rate-limited.
- A simple in-memory per-session rate limit on agent endpoints, to protect the quota.
- CORS: no wildcards, an env allowlist, and same-origin by default (dev proxy, with the built frontend served by the backend).
- If MCP is exposed: Origin validation and localhost binding per the verified spec.

**4.7 Budgets (engineering targets, with measured values recorded in the test doc rather than assumed).**

- cold start of both services ≤ 15s
- non-LLM API p95 ≤ 200ms locally
- deterministic agent turn ≤ 1.5s
- live agent turn p95 ≤ 10s, with a hard timeout
- provider-outage recovery visible to the user within timeout + 1s
- confirm action in 1 click
- session reset and seed ≤ 2s
- a clean clone to demo-ready in ≤ 10 min, and ≤ 60s when already installed
- video 150–170s

**4.8 Windows-safe commands.** Make commands PowerShell-safe (`curl.exe`, not `curl`; no `&&` or bash heredocs). Provide single-entry commands for dev, test, smoke, `contract:check` and seed.

## 5. Product spec requirements (`docs/01_PRODUCT_SPEC.md`)

- **Pitch, user, pain point.** Include a one-sentence pitch, the target user and pain point, and why this belongs on an ambient multimodal surface rather than a web form or chat window.
- **Surface design.** An Echo-Show-style visual surface, not a transcript. It includes:
  - an utterance bar (typed is first-class; voice and TTS are P1)
  - a spoken-style response line
  - a Plan Preview card showing the diff
  - a schedule timeline
  - a primary Confirm and a Cancel
  - a collapsible tool trace
  - the provider mode badge
  - a visible “Remembered” memory element
- **Golden Demo, the primary product contract.** One exact scenario containing:
  - the seeded start state, defined once in a seed file referenced by tests and reset
  - exact utterances for Turn 1, the approval, an interruption turn with replan and approval, and a follow-up after page reload or session restore
  - the expected agent decisions and tools invoked
  - the expected row-level database mutations
  - the visible UI changes at each step
  - cross-session memory written on approval and used later
  - the expected failure and fallback behavior
- **Live-LLM acceptance.** Because live output varies, live runs are verified by invariants (no overlaps, completed blocks preserved, deadline-critical work scheduled, within available hours, a valid plan state). Exact wording is not asserted.
- **Scope tiers and anti-scope.**
  - **P0:** everything the golden demo, the mandatory video claims and the submission need.
  - **P1:** polish, voice and TTS, extra tool depth, MCP inspector panel, hosted deployment unless the rules require it (then P0).
  - **P2:** optional adapters, forbidden after the freeze.
  - **Anti-scope:** auth/OAuth, multi-tenant cloud DB, mobile wrappers, paid SaaS.

## 6. Plan, task board and milestones

**6.1 Vertical slice first (mandatory).** The first engineering milestone, M1, delivers a tiny but complete running loop: **utterance → API → real tool(s) → SQLite → approval → state mutation → visible UI update**. It includes at least one real READ tool and one real COMMIT tool of the chosen concept, the deterministic provider, the generated contract types and `contract:check`, session isolation, and the seed and reset. Complexity is added only after that loop is verified.

The repo must contain a runnable app at the end of every milestone. Horizontal sequencing (all backend, then all frontend, then integration) is invalid. Suggested milestone shape, adjustable to the runway profile:

- M1: walking skeleton.
- M2: full golden path on deterministic, including interrupt and replan, memory and the real UI.
- M3: live Gemini provider, resilience and the security hardening.
- M4: submission pathway (see §8), running in parallel from the end of M2.
- M5: P1.
- M6: freeze, final video, submission.

Tag each milestone in git (`m1-slice`, and so on).

**6.2 Task board (`docs/04_TASK_BOARD.md`).** The board is the actionable heart.

- It holds 20–30 tasks, each 20–60 minutes for its owner. Human tasks are time-boxed, and recording tasks may be longer.
- The header holds a STATE block (current milestone, last verified commit, active locks, agent mode) that Gemini updates, so work is resumable after context loss.
- Status values are `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `SKIPPED`. `TODO` is valid.
- Each task uses this block:
  - `ID`, `TITLE`
  - `OWNER` (GEMINI | CODEX | HUMAN)
  - `PRIORITY`
  - `TRACK` (BUILD | SUBMIT for P0)
  - `STATUS`
  - `DEPENDS`
  - `PARALLEL-SAFE-WITH` (only if file sets are disjoint and contracts are frozen)
  - `FILES` (exact paths)
  - `SPEC REFS` (section pointers into 01, 02 or 06, never copied schemas)
  - `READ ONLY` (the sections the executor needs)
  - `IMPLEMENT` (concrete classes, functions, endpoints or UI elements)
  - `ACCEPTANCE` (each criterion names an observable and an expected result; vague criteria are not allowed)
  - `VERIFY` (an exact PowerShell-safe command)
  - `DO NOT`
  - `BLOCKS` (for Human tasks: which tasks they block, or none)
- Priority semantics:
  - **P1 may start once all P0 BUILD tasks are DONE.**
  - P0 SUBMIT tasks are scheduled by dependencies and time anchors and preempt P1 whenever unblocked.
  - Submission and demo tasks are P0 from the start. They include README upkeep as part of each milestone’s definition of done, an early rehearsal recording, a deployment rehearsal if hosted, final recording, upload buffer and Devpost verification.
  - Human approvals block only the tasks listed in their `BLOCKS` field. Unrelated work continues.
- Every P0 mandatory video capability must be achievable from P0 tasks alone.
- P1 work merges only if it passes the full P0 smoke test. Otherwise it is discarded at the freeze.

**6.3 Schedule (`docs/03_MASTER_PLAN.md`, short).** Include the backwards plan using the profile from §2, with T-minus anchors and IST times. It sets:

- the target for the first working end-to-end prototype
- a mid-point checkpoint (if the vertical slice or P0 is behind at the checkpoint, trigger the cut-down)
- a hard feature freeze (T-8h, or T-6h if R < 24h)
- the submission-ready line (T-3h)
- the deployment rehearsal
- the early demo rehearsal recording
- a final video upload buffer
- a Devpost verification buffer
- the **Minimum Valid Submission pathway**: the smallest set of files, README, video and forms that satisfies every mandatory deliverable, achievable from M1 and M2 alone
- an ordered **emergency cut-down ladder** that always preserves primary-track eligibility. Suggested order: hosted deploy → voice and TTS → MCP if B is the basis → live provider (deterministic only, stated honestly) → UI polish, retaining the golden-path replan

## 7. Agent protocol (`docs/05_AGENT_PROTOCOL.md`, a single document for both agents)

**7.1 Codex integration preflight (Gemini’s first action, before any delegation).**

- Do not assume integrations exist. Check what is actually available: a Codex CLI or extension, and whether Gemini can invoke it non-interactively.
- Run a harmless smoke delegation: ask Codex to create `handoff/codex_ping.txt` with fixed content, verify the file exists, then delete it.
- Record `AGENT_MODE: DIRECT` or `AGENT_MODE: MANUAL_HANDOFF` in the STATE block and in the decisions log.
- If MANUAL\_HANDOFF: Gemini writes `handoff/TASK-XXX.md`, the Human pastes it into Codex, Codex writes `handoff/TASK-XXX.report.md`, and the Human tells Gemini. `handoff/` is gitignored except `.gitkeep`.
- If Codex is unavailable entirely, Gemini executes P0 tasks directly at the smallest scope and informs the Human.

**7.2 Operating rules.**

- Task and file ownership are explicit. Only one agent edits a file at a time. Parallel work is allowed only for tasks flagged `PARALLEL-SAFE-WITH`. There are no uncontrolled parallel edits.
- One task per Codex invocation. One git commit per verified task (`TASK-XXX: title`), plus milestone tags.
- Context economy: read the protocol once per session, then only the board and the `READ ONLY` sections for the current task. The handoff contains the verbatim task block, copied excerpts of the referenced sections, a standing-rules block of at most 20 lines, and the required report format. Codex must not read other docs unless the handoff says so. If the contract is unclear, Codex stops and returns `CONTRACT_GAP`, and does not improvise.
- **Independent verification.** A Codex report is a claim, not proof. Gemini re-runs the `VERIFY` command itself, checks the diff only touches the allowed files, and runs `contract:check` and the golden smoke test when shared behavior changed. Anti-fake checks:
  - Grep for demo content hard-coded outside the deterministic provider and the seed.
  - Confirm UI data comes from the API.
  - Confirm tool results derive from DB state.
  - Verify claims by querying SQLite, not by reading code.
- **Failure ladder.** On the first failure, send Codex the exact error and diff. On the second, reduce the scope or split the task on the board, or have Gemini do it directly if it is small. On the third, restore the last checkpoint with `git restore` (clean only task-owned untracked files after listing them), mark the task `BLOCKED` and notify the Human, then continue unblocked tasks.
- Friction: when real friction occurs (Amazon, MCP or agentic tooling), log it in `docs/07_FRICTION_LOG.md` with evidence at the time it occurs.
- Include the Codex completion report format: files changed, commands run, test output summary, edge cases, contract gaps.
- Include the quota and context fallback: board state and handoff files let any agent resume.
- **Optional Opus audit (the only permitted second Opus call).** Include the trigger conditions and a ready-to-paste prompt of at most 40 lines. It is read-only and takes the docs, test results and a git summary. It finds submission and contract risks and returns a one-page findings list. It never writes code. Work must not depend on it.

## 8. Test, demo and submission (`docs/06_TEST_DEMO_SUBMISSION.md`, one document)

- The test strategy:
  - tool unit tests
  - API-level agent loop tests (message → plan → confirm → state → session persistence)
  - the golden smoke test as one command, covering deterministic mode, live mode via invariants, and the fallback path
  - the injection test
  - the idempotency test
  - the stale-plan test
  - the UI: build and typecheck plus a Human checklist of no more than 5 minutes. A Playwright test is optional P1.
- Gates: MVP CODE COMPLETE, DEMO READY, SUBMISSION READY. All are checklists with commands.
- The budget results table, with columns for target, how it is measured, and the measured result.
- **Video claim map:** a table of claim | mandatory or optional | task IDs | verification step. Include the video script with timings (≤170s hard cap) and the Human recording steps. The first 15 seconds must state the problem and the value. The video must accurately state simulation versus MCP.
- The Devpost kit: section templates, built-with tags, the testing instructions, and the product feedback text derived from the friction log. Claims in it are checked against the claim map at the end.
- Pre-submission audit: secret scan, repo access, LICENSE (MIT), screenshots, public video link check, English check, README verification.

## 9. Logs and the remaining files

- `docs/07_FRICTION_LOG.md`: the field schema (ID, timestamp, component, task, steps, expected, actual, severity, workaround, recommendation). Seed it **only** with friction you actually encountered in this session, with evidence. If there was none, state that and leave no entries. Never fabricate any.
- `docs/08_RISKS.md`: a lightweight top-8 table (risk, probability, impact, built-in prevention, trigger, fallback, latest safe decision time). Cover LLM quota or outage, MCP transport issues, schema drift, malformed tool args, scope creep, Windows issues, voice API support and ephemeral hosting.
- `docs/09_DECISIONS.md`: ADRs and the runtime-decisions section.
- `README.md`: a skeleton with a small high-level Mermaid diagram, quickstart, an honest track-alignment section, and clear mode statements. Update it continuously. `docs/02` holds the detailed diagrams, and the README does not duplicate its specifications.
- `AGENTS.md` (optional pointer, no content duplication): at most 10 lines pointing agents to `docs/05_AGENT_PROTOCOL.md` and the task board. Do not assume Gemini reads it. The Human tells Gemini where to start.
- `docs/00_PROJECT_CONTEXT.md`: at most about 80 lines. It covers the facts (§1), the chosen approach and concept, the golden rule, and an index of what each doc governs. It is the single entry point.
- `.gitignore` (stack, OS, `.env`, SQLite files, build output, `handoff/*` except `.gitkeep`), `.env.example`, `LICENSE`.

Approximate size budgets: 00 ≤ 80 lines, 01 ≤ 200, 02 ≤ 600, 03 ≤ 100, 04 ≤ 700, 05 ≤ 250, 06 ≤ 200, logs ≤ 60 each.

## 10. Writing order (so an interruption still leaves a usable core)

1. `docs/00_PROJECT_CONTEXT.md`
2. `docs/01_PRODUCT_SPEC.md`
3. `docs/02_ARCHITECTURE.md`
4. `docs/04_TASK_BOARD.md`
5. `docs/05_AGENT_PROTOCOL.md`
6. `.gitignore`, `.env.example`
7. `docs/03_MASTER_PLAN.md`
8. `docs/06_TEST_DEMO_SUBMISSION.md`
9. `README.md`, `LICENSE`, `AGENTS.md`
10. `docs/09_DECISIONS.md`, `docs/08_RISKS.md`, `docs/07_FRICTION_LOG.md`

After each file, confirm it exists (listing plus a read-back of its head and tail). Do not assume a write succeeded.

## 11. Writing standards

- Every file is concrete and project-specific. A planning document may contain future steps.
- Specifications contain no unresolved questions and no vague acceptance criteria. The words “TBD” and “to be decided” never appear. “TODO” appears only as a valid task status value.
- Each fact has one authoritative home. Other files reference it by file and section.

## 12. Validation before finishing

Run checks in the shell (a throwaway command, or a small stdlib-only `scripts/check_docs.py` that Gemini can reuse after board edits, using whichever runtime is verified):

1. Task dependency graph: every `DEPENDS` ID exists, there are no cycles, and the order is topological.
2. Every `SPEC REFS` target section exists.
3. Every table, endpoint and tool name used in 01, 04 and 06 exists in 02. Every env var in `.env.example` exists in 02’s config table.
4. Every mandatory video claim maps to P0 tasks and a verification step.
5. The M1 vertical-slice tasks contain the complete loop, and the repo is runnable at each milestone boundary.
6. Submission and demo tasks are P0 and scheduled. The MVSP and the cut-down ladder preserve the mandatory deliverables.
7. The track claim is consistent across 00, 01, 06, the README and the decisions.
8. A forbidden-marker lint passes. Commands are PowerShell-safe.
9. The friction log contains no fabricated entries.

Fix everything you find. Then commit (`docs: architecture handoff`) if git is working. **Stop.** Do not begin implementation.

## 13. Final chat report (at most about 25 lines, factual)

- Product name and the one-sentence pitch, and why it won.
- The chosen track approach (A, B or C), the stack, and the scope profile with R.
- The task counts by priority.
- Top 3 risks and their built-in mitigations.
- The exact first instruction for Gemini (the AGENT\_MODE preflight, then the first task).
- **Verified files:** each path with line count and the validation results. **Unfinished or unverified items,** listed explicitly (anything that failed validation, could not be written, or depends on an unverified assumption).

## 14. Final Architecture Safeguards — Mandatory

These requirements override conflicting instructions above.

**A. Live AI is the intended competitive experience.** Design the P0 golden path to work with a real, accessible LLM provider, preferably Gemini after actual API availability is verified. Deterministic mode is mandatory for testing and resilience, but must never be represented as live model reasoning. If real-model integration cannot be completed by the emergency deadline, preserve a truthful, functional submission and explicitly assess whether it still satisfies Alexa+ eligibility.

**B. Do not predetermine the concept tournament.** Candidates must have a meaningful stateful, multi-step agent capability with persistent context and user-visible consequences. Interrupt-and-Recover Planning is one strong possibility, not a compulsory feature for every candidate. The winning concept must be selected on judging impact, actual feasibility and demo reliability.

**C. Apply a complexity budget.** Use the simplest implementation that achieves the required behavior. A feature does not become mandatory merely because it is named in the architecture requirements. Prefer straightforward error handling to an elaborate circuit breaker, small shared contracts to heavyweight code generation, and a single reliable workflow to generalized agent infrastructure. Document genuinely necessary exceptions.

**D. Clarify domain-state versus proposal-state mutation.** READ tools never mutate data. PROPOSE tools may persist draft proposals and audit metadata but cannot change committed user tasks or schedules. COMMIT tools change domain state only after explicit authorization. Domain-state versioning must not invalidate a proposal merely because it was stored. Repeated confirmations must not execute tools twice.

**E. Define memory precisely.** Distinguish same-session conversation history, browser-reload restoration and persistence across distinct conversations. Do not claim cross-session memory unless the implementation genuinely retrieves previously committed context through a stable, authorized identity or workspace boundary.

**F. Preserve failure evidence.** If an atomic database commit fails, roll back domain mutations first, then record the failure in a separate safe logging operation. Do not claim that records written inside a rolled-back transaction remain persisted.

**G. Protect the minimum valid submission.** The emergency pathway must preserve a working, genuinely agentic Alexa+ simulation and all mandatory submission materials. If the signature feature cannot be completed safely before feature freeze, simplify it rather than sacrifice the entire project. Do not present incomplete functionality as working.

**H. Separate architecture validation from implementation validation.** During this planning-only session, verify that documents, dependency graphs, file references and commands are internally consistent. Do not claim that application tests, API behavior, provider integrations or milestone runtime checks have passed before the application exists. Record these as future execution gates.

**I. Verify practical API access early.** The task board must contain an early Human/Gemini check for a usable LLM API key, model availability, free-tier limits and response latency. Subscription access to Gemini or a coding IDE does not automatically imply access to corresponding API inference.

**J. Enforce a planning-output budget.** Critical architecture, contract and task documents take priority. Avoid duplicating lengthy specifications or producing unnecessary boilerplate. A concise, complete plan is superior to thousands of lines that exhaust the architect's context or become difficult for Gemini Flash to maintain.