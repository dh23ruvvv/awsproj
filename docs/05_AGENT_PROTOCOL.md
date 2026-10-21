# FlowPilot — Agent Protocol

> Single document for both Gemini (Coordinator) and Codex (Executor).

## 1. Codex Integration Preflight

**Gemini's first action before any delegation.**

1. Check if Codex CLI exists: `Get-Command codex -ErrorAction SilentlyContinue`
2. Smoke test: ask Codex to create `handoff/codex_ping.txt` with content `FlowPilot Codex integration verified`
3. Verify file: `Get-Content handoff/codex_ping.txt`
4. Clean up: `Remove-Item handoff/codex_ping.txt`
5. Record result:
   - **DIRECT:** Codex responds programmatically. Gemini delegates via CLI.
   - **MANUAL_HANDOFF:** Codex is available but not automatable. Gemini writes `handoff/TASK-XXX.md`, Human pastes into Codex, Codex writes `handoff/TASK-XXX.report.md`, Human tells Gemini.
   - **GEMINI_ONLY:** Codex unavailable. Gemini executes P0 tasks directly at smallest scope.
6. Update `docs/04_TASK_BOARD.md` STATE block and `docs/09_DECISIONS.md`.

`handoff/` is gitignored except `.gitkeep`.

## 2. Task Ownership Rules

- Only one agent edits a file at a time.
- Parallel work allowed only for tasks flagged `PARALLEL-SAFE-WITH` (disjoint file sets, contracts frozen).
- One task per Codex invocation.
- One git commit per verified task: `TASK-XXX: title`.
- Milestone tags: `m1-slice`, `m2-golden`, `m3-live`, etc.

## 3. Context Economy

Agents read the protocol once per session, then only:
- `docs/04_TASK_BOARD.md` STATE block + current task block
- The `READ ONLY` sections listed in the task

### Codex Handoff Format

```markdown
# TASK-XXX: [Title]

## Task Block
[Verbatim copy of the task from 04_TASK_BOARD.md]

## Referenced Sections
[Exact excerpts from the files listed in READ ONLY, max needed content]

## Standing Rules (max 20 lines)
1. Use only the files listed in FILES.
2. Do not read docs not listed in READ ONLY.
3. If the contract is unclear, stop and return CONTRACT_GAP.
4. Do not improvise schemas, endpoints, or tool definitions.
5. All DB access uses parameterized queries.
6. All new code includes docstrings.
7. Run the VERIFY command before reporting done.
8. Use PowerShell-safe commands only.
9. Do not modify files not in your FILES list.
10. Report using the format below.

## Required Report Format
Write to `handoff/TASK-XXX.report.md`:
- FILES_CHANGED: [list]
- COMMANDS_RUN: [list]
- TEST_OUTPUT: [summary]
- EDGE_CASES: [discovered]
- CONTRACT_GAPS: [any unclear specs, or NONE]
```

## 4. Independent Verification (Gemini's responsibility)

A Codex report is a claim, not proof. After every task:

1. Re-run the `VERIFY` command.
2. Check `git diff` only touches allowed FILES.
3. Run `contract:check` if shared types or schemas changed.
4. Run golden smoke test if shared behavior changed.
5. Anti-fake checks:
   - `Select-String -Path server/**/*.py -Pattern "quarterly report|Plan my day" -Exclude "*deterministic*","*seed*","*fixture*"` — no hard-coded demo content outside provider/seed.
   - Confirm UI data comes from API responses (check fetch calls in components).
   - Confirm tool results derive from DB queries (check SQL in tools).
   - Verify DB state by querying SQLite directly, not by reading code.

## 5. Failure Ladder

| Attempt | Action |
|---|---|
| 1st failure | Send Codex the exact error message and diff. |
| 2nd failure | Reduce scope or split task on the board. Or Gemini does it directly if small. |
| 3rd failure | `git restore` to last checkpoint. Clean task-owned untracked files (list first). Mark task BLOCKED. Notify Human. Continue unblocked tasks. |

When restoring: `git stash; git checkout HEAD -- [files]` or `git restore --source HEAD -- [files]`. Only clean untracked files that belong to the failed task's FILES list.

## 6. Friction Logging

When real friction occurs with Amazon services, MCP tooling, or agentic tooling:
- Log immediately in `docs/07_FRICTION_LOG.md`
- Include evidence (error messages, screenshots, timestamps)
- Do not fabricate entries. If no friction, don't log.

## 7. Quota & Context Fallback

If Gemini or Codex runs out of context or quota:
- Board STATE block and handoff files let any agent resume
- Each task is self-contained with its READ ONLY sections
- A new agent session reads: `docs/04_TASK_BOARD.md` STATE → current task → referenced sections

## 8. Optional Opus Audit

**Trigger conditions:** Use only if:
- Multiple P0 tasks are BLOCKED with no clear resolution
- Contract drift detected that Gemini cannot resolve
- T-12h and submission readiness is uncertain

**Ready-to-paste prompt (≤ 40 lines):**

```
You are a read-only auditor for FlowPilot, an Alexa+ hackathon project.

Inputs (attached or in workspace):
- docs/00_PROJECT_CONTEXT.md through docs/09_DECISIONS.md
- Latest test results (pytest output)
- git log --oneline -20
- git diff --stat HEAD~5

Tasks:
1. Check submission readiness against docs/06_TEST_DEMO_SUBMISSION.md gates.
2. Check contract consistency: do endpoints in 04 tasks match 02 schemas?
3. Check video claim map: can every claim be demonstrated from DONE tasks?
4. Check risk triggers: have any docs/08_RISKS.md triggers fired?
5. Check track alignment: is the Alexa+ claim honest across all docs?

Output: A single findings list with severity (CRITICAL/WARNING/INFO).
- CRITICAL = submission at risk
- WARNING = quality issue
- INFO = suggestion

Do not write code. Do not modify files. Return findings only.
```

This audit is optional. No work depends on it.
