# Release progress

| Work | Owner | Status | Verification |
|---|---|---|---|
| Forensic audit | root | DONE | Working tree, code, scripts, initial test execution |
| Duration-based scheduler | scheduler agent + root | DONE | Full-duration, overlap, immutable/in-progress and capacity regressions |
| Honest offline parsing | provider agent | DONE | Explicit interruption intervals; unsupported commands explained |
| Task API / approval safety | root | DONE | CRUD, versioning, task ownership, protected identities, deadlines and atomicity tests |
| UI lifecycle and task controls | UI agent + root | DONE | Typecheck/build and real browser journey |
| Integration / browser verification | root | DONE | 203 passed, 2 live tests skipped; desktop/mobile browser and direct SQLite checks |
| README / demo / submission package | provider agent + root | DONE | Final labels, launch commands, client meeting setup and official rules checked |
| Record/publicly upload video | HUMAN | TODO | Public YouTube/Vimeo link, under three minutes |
| Share repository and finalize Devpost | HUMAN | TODO | Accessible repository and submitted-state confirmation |

No existing user data reset, deployment, submission or commit performed.

## Final verification (Windows, October 22, 2026)

- `npm.cmd test -- --tb=short -q`: **203 passed, 2 skipped**. Skips are explicit live-API tests; dependencies emit deprecation warnings. A key alone no longer triggers live requests; `FLOWPILOT_RUN_LIVE_TESTS=1` is also required.
- `npm.cmd run smoke`: **2 passed, 1 live test skipped**.
- `npm.cmd --prefix frontend run build`: **PASS**, including TypeScript `tsc --noEmit`. No independent frontend lint script is configured.
- `npm.cmd run contract:check`: **PASS**. OpenAPI and generated frontend types match. Repaired the script to use its installed frontend dependency; the old root `npx` attempted an unnecessary blocked registry request.
- `python scripts/browser_release.py --url http://127.0.0.1:8013`: **PASS**, headless installed Chrome, 1440px desktop and 390px mobile. Checks task create/edit/remove; proposal reload; cancel safety; confirmation matches review; refresh persistence; explicit interruption; fixed client meeting; recoverable protected-event conflict; new workspace preserves previous session; no JavaScript exceptions or horizontal overflow.
- Direct SQLite inspection of `data/release-final-verification.db`: **PASS**, two preserved sessions, final session seven nonoverlapping blocks, all linked task durations complete, 15:30 protected client meeting, version 6.
- `git diff --check`: **PASS** (Git emits existing Windows line-ending notices).
- Credential-pattern scan of 126 tracked/new source files: no matches for standard Google/AWS/GitHub key or private-key patterns, and no tracked `.env` or `.env.local`. This is a targeted scan, not a security audit or history scan.
- Backend static frontend serving was exercised through real HTTP on isolated test databases. Live Gemini inference was not verified. Fresh-machine Python dependency installation was not performed; README distinguishes this from observed local start/build.

Screenshots are local, gitignored artifacts in `data/browser-release/`: `desktop-home.png`, `desktop-proposal.png`, `desktop-client-confirmed.png`, `mobile-confirmed.png`. Regenerate with the browser script before sharing.

## Resulting behavior and changed paths

- Backend: `server/engine/{scheduler,validator,differ,task_validation}.py`, `server/tools/{propose_tools,commit_tools}.py`, `server/routers/{agent,tasks,commitments}.py`, `server/providers/{deterministic,gemini,fallback}.py`, `server/{config,database,main,models}.py`, `server/seed.json`.
- Frontend: `frontend/src/App.{tsx,css}`, `frontend/src/api/{client,types}.ts`, task/fixed-event editors, TaskList, ScheduleTimeline, PlanPreview, ResponseLine and UtteranceBar components/styles. Removed the pending-task Schedule button whose utterance was unsupported in offline mode. New demo workspaces retain previous data.
- Verification/contracts: new `tests/test_release_{api,provider,commitments}.py`; updated engine, provider, lifecycle, proposal, session and smoke regressions; `scripts/{browser_release.py,contract_check.ps1,dev.ps1,smoke.ps1}`, `generated/openapi.json`.
- Setup/package: `.env.example`, `.gitignore`, `requirements-dev.txt`, `package.json` (MIT metadata matches LICENSE), `README.md`.
- Release documents: `docs/RELEASE_GAP_AUDIT.md`, this progress file, `docs/DEMO_SCRIPT.md`, `docs/DEVPOST_SUBMISSION.md`.
- Preexisting AGENTS/audit/planning changes were preserved. No git commit was created.

## Scope boundaries and remaining risks

The reproducible offline demo is implemented and tested; the original prompt's full ambition is **not 100% complete**. Free-form new-task extraction is unfinished: task creation uses explicit controls in both providers. The offline planner has fixed 09:00-17:00 hours, same-day requests and contiguous greedy placement; it safely rejects some requests that a more flexible solver could fit. Scheduled tasks cannot be directly edited/removed, there is no completion control, and no workspace-history picker or production authentication exists. These limits are stated in README and submission copy. Successful live Gemini inference, fresh-machine dependency installation, public hosting, repository publication, video upload and final submission are not claimed.

The next human action is to rehearse `docs/DEMO_SCRIPT.md`, record and publicly upload the actual flow, review repository access and the submission placeholders, then complete Devpost's final submission before the official deadline.


## Personal day planner update

- Replaced automatic demo initialization with an empty personal workspace and isolated, persisted date sessions. Retained existing data and legacy seeded API routes.
- Removed execution trace UI. Plan my day opens setup; interruptions require a user-supplied name and time interval.
- Added SQLite-backed weekday routines with multi-task input, start date, stop control, per-day deduplication, and deferred application during pending proposal review.
- Kept black-and-white pixel styling. Date picker computes weekdays and preserves selected day on refresh.
- Verified: 206 backend tests passed, 2 live-provider tests skipped; frontend production build and OpenAPI contract passed. New browser_personal_days.py passed guided planning, approval/cancel/reload, named interruption, routine weekday matching, day isolation, no duplicates, no browser exceptions and 320-1440px overflow checks.
- Bounds: 09:00-17:00 planner; routine tasks populate when matching days are opened; routine times remain flexible until a plan is approved. No background scheduler, notifications or cross-device login.
