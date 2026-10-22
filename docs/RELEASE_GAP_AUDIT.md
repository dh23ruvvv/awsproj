# Release gap audit — 2026-10-22

Verified from the working tree, not assumed from older plans. Preexisting edits in AGENTS, frontend, scheduler, differ, models, database, providers, proposal/commit tools and tests are retained.

- Stack: FastAPI/Pydantic, SQLite, React/TypeScript/Vite. Root scripts expose `npm run dev`, `npm test`, `npm run build`, `npm run smoke`, `npm run contract:check`. Direct launch is `python -m uvicorn server.main:app --port 8000` and `npm --prefix frontend run dev`.
- Valuable foundations: isolated sessions, proposal storage, savepoint-based commit, repeat-confirm handling, fixed-block validation, API envelopes, provider abstraction, and integration tests.
- Confirmed scheduling defects: 55/60/45 minute focus reservations overallocate estimates; personal tasks truncate to 45 minutes. Demo-only buffer/planning blocks obscure actual capacity. Replace with full-duration interval fitting and recoverable capacity errors.
- Confirmed product gaps: no task mutation endpoints; deterministic interruptions ignore explicit times and always insert a 30-minute manager meeting; narrative claims specific outcomes without deriving them. Frontend lifecycle requires repair and usable task controls.
- Trust gaps: agent request reads but ignores client version; commit trusts stored proposals without revalidating protected intervals; keyword-based memory invents preferences. Preserve transaction architecture and strengthen validation.
- Documentation overclaims a fixed test count and contains speculative integrations. Requirements omit test/live SDK installation. Environment-file loading needs verification.
- Initial broad pytest attempt encountered local temporary-directory permission errors; use an explicit workspace test directory. Focused proposal tests execute and expose obsolete pinned timetable assertions.
- Available skills are imagegen, OpenAI docs, skill tooling, plugin management, Sites and Work Pets. No specialized local backend/debugging/accessibility skill is provided. Sites targets hosted Sites workflows; this task retains the existing local React application. No browser automation connector is exposed; probe installed Playwright separately.

Retain the stack and working components. Refactor scheduler/provider, add versioned task controls, strengthen approval safety, then verify tests/build and document observed behavior. Competition eligibility and external submission remain subject to official rules and user action.
