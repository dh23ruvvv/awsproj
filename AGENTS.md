# FlowPilot — Repository Agent Contract

This file governs AI coding agents operating in this repository. Read it first. It supersedes conflicting instructions in older project planning documents, but does not supersede system/developer instructions or safety requirements.

## Mission / definition of success

Ship **FlowPilot**, a compelling, genuinely functional, judge-ready **simulated Alexa+ agentic day-planning experience** for the Build, Ship, Shape: Amazon Developer Hackathon 2026. The entrant's intended primary track is Alexa+ via the explicitly allowed simulated-experience route, **not** a claim of official Alexa+ SDK integration. The submission deadline is **October 23, 2026 at 12:00 PM Pacific / October 24 at 12:30 AM IST**. The exact official rules take precedence: https://amazonappdev2026.devpost.com/rules

Our desired customer story: a busy person tells FlowPilot about their tasks, priorities, commitments and interruptions; the agent understands the request, produces a realistic conflict-free day plan, protects fixed events and completed work, clearly explains changes, and **only applies calendar modifications after explicit user approval**. The user can actually interact with the app to do this; a pretty but fake dashboard is not acceptable.

## Product outcome (do not optimize only for green tests)

1. **Plan:** add/manage tasks with real duration, priority and deadlines; generate a usable schedule from tasks and existing protected events.
2. **Adapt:** accept an unexpected interruption in plain language; replan flexibly around immutable commitments and actual availability; never silently truncate, lose, or overlap tasks.
3. **Explain and approve:** show a truthful before/after preview (added, moved, duration changed, removed, unable to schedule); require confirmation before commit; cancel must leave persistent schedule unchanged.
4. **Trust:** preserve block identity and task associations; validate timestamps/timezones, constraints, session versions and transactions; give clear, recoverable failures.
5. **Present:** deliver a cohesive, polished, responsive desktop/mobile experience with excellent hierarchy, purposeful states and accessible interactions. Distinguish live AI from deterministic fallback and clearly identify the product as an Alexa+-inspired simulation.
6. **Demonstrate:** a reproducible end-to-end flow from a clean checkout with no hidden developer-only steps, secrets, mock-only buttons or fabricated outcomes.

## Operating procedure

- Begin with `git status --short`, repository structure, package/config files, running instructions, key backend/frontend entry points, tests and real user journeys. Identify existing valuable functionality before rewriting it. Review relevant documents (`README.md`, `docs/04_TASK_BOARD.md`, `docs/05_AGENT_PROTOCOL.md` and architecture/specification as useful) **as evidence, not as unquestionable authority**; stale TODOs must not override the mission above.
- Inspect code beyond the old task board when necessary. The former instruction to read *only* specified document sections is lifted for this release overhaul. Keep context selective and focused.
- Discover and use genuinely available local skills for frontend design, backend engineering, debugging, testing, accessibility and secure review where relevant. Read their actual instructions before using them. Never invent installed skills or pretend they ran.
- Produce a short evidence-based gap assessment, then **implement** in priority order; do not stop after planning. Prefer targeted, well-tested refactors over sweeping rewrites, new infrastructure or unnecessary dependencies.
- Preserve the core **READ -> PROPOSE -> HUMAN APPROVAL -> COMMIT** separation. An AI-generated response must never directly commit a schedule.
- Implement a complete vertical slice first: user request -> real agent/tool path -> valid schedule proposal -> visual diff -> user confirmation -> persisted calendar. Then improve polish and edge cases.
- Work in verifiable increments. Run relevant tests/builds after each logical change, repair introduced regressions and report actual results. If no tests exist, add focused automated tests around high-risk behavior.
- You may remove redundant, misleading or unused code and obsolete UI only **after** tracing references and confirming no important functionality will be lost. Avoid disruptive architecture churn; use migrations if persistence must change. Do not casually delete project files, data, dependencies, history or docs.
- Do not run destructive Git commands (`reset --hard`, `clean -fd`, force pushes), overwrite user work, leak secrets, incur cloud charges, deploy externally or submit Devpost without explicit user authorization. Never copy keys into commits or logs.
- Do not claim a bug is fixed unless tests or a reproducible manual check support it. Clearly differentiate verified facts, hypothesized issues and untested claims. Do not claim the project is "bug-free" or "guaranteed to win."
- Keep `README.md` and project documentation consistent with **what runs**, not aspirations. Do not invent AWS/Bedrock/MCP/Bee/Ring integration. AWS Builder and Open Source mini-challenges are optional and require their own real eligibility evidence.

## Release priorities

**P0:** correct end-to-end demo; no invalid schedule, hidden task truncation, data loss, unintended commits or crashes on normal interruptions; build/run succeeds; judges can reproduce it.

**P1:** coherent interface and conversational UX; truthful diffs; useful errors, loading/empty states; session recovery; automated regression coverage; demo data/reset mechanism; clear setup documentation.

**P2:** preference personalization, optional voice UX or extra integrations *only if* P0/P1 are genuinely stable and there is time. Don't confuse scope growth with product quality.

## Competition packaging

Before calling the app submission-ready, verify: an appropriately accessible GitHub repository with all code/assets/setup steps and license/sharing requirements; an **under-3-minute public YouTube or Vimeo video showing the actual working web simulation**; clear English project description and tool/API/SDK product feedback; primary track selection; any applicable testing credentials; and actual evidence for any claimed mini-challenge. Friction logs are optional but can contribute a judging bonus. A Devpost *draft* is not a final submission.

## Completion protocol

At each significant checkpoint report only: **Completed; Files changed; Commands/tests and outcomes; Remaining risks/blockers; Next highest-priority action**. Use concise factual updates. If blocked by a missing key, dependency, account or permission, implement and verify all independent work and state the exact blocker. When finishing, provide exact local run commands and a judge-ready demo script. Never hide unfinished work behind optimistic language.
