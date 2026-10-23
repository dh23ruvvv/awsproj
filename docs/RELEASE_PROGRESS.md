# Release verification

## Final verification gate — October 23, 2026

| Exact command | Result |
| --- | --- |
| `python -m pytest tests/ -q -p no:cacheprovider --basetemp .test-tmp-final` | 263 passed, 3 skipped, 18 warnings in 34.48s |
| `npm.cmd --prefix frontend run build` | TypeScript passed; Vite 8.3.5 transformed 43 modules; built in 199ms |
| `npm.cmd run contract:check` | Contract check passed: types are in sync. |
| `npm.cmd run smoke` | 2 passed, 1 skipped, 2 warnings in 1.47s; Golden Smoke Test PASSED cleanly! |

The three submission-readiness commands exited 0. The smoke result above is from
the earlier verification, whose stdout/stderr is saved locally in the ignored
`data/release-verification.txt`. The first smoke attempt encountered Windows
permissions on a reused `.test-tmp-smoke` directory. The runner now uses pytest's
fresh temporary directories; the final command above passed. Existing temp
directories and user databases were not deleted.

Encoding audit: 118 source/documentation files, zero mojibake sequences and zero
UTF-8 BOMs. `git diff --check` passed. The final build also includes the grayscale
styling correction for expanded tool traces and the linked-session return link.

The offline suite skips the three explicitly opt-in live tests. Dependency
warnings concern Starlette's httpx integration, the HTTP 422 constant and Google's
SDK typing; no application test failed in the final run.

## Live Gemini evidence

All tests used a 30-second model-turn budget and isolated test databases.

| Check | Exact result |
| --- | --- |
| Task drafting with requested `gemini-2.5-flash` | 1 failed, 14 deselected, 2 warnings in 3.13s; Google HTTP 404: model no longer available to new users |
| Task drafting with `gemini-3.5-flash-lite` | 1 passed, 14 deselected, 2 warnings in 3.65s |
| Read-tool inference with `gemini-3.5-flash-lite` | 1 passed, 38 deselected, 2 warnings in 9.51s |
| Strict live calendar smoke with `gemini-3.5-flash-lite` | 1 passed, 2 deselected, 2 warnings in 15.31s |

The requested source default remains `gemini-2.5-flash`; the ignored local
`.env` selects the verified `gemini-3.5-flash-lite` override. Credentials remain
in the environment. No keys were printed or added to tracked files.

A stricter live calendar test exposed a model omission of a saved task.
Whole-day requests now use the shared scheduler through `propose_schedule`,
ensuring complete task coverage and preferences. Custom task-selection requests
continue to use validated custom proposals. The final live smoke requires
Gemini itself, a real proposal and successful invariant checks; fallback alone
cannot satisfy it.

## Browser evidence

- `python scripts/browser_personal_days.py --url http://127.0.0.1:8017`: PASS.
  Empty start, guided planning, review/reload/cancel/confirm, named interruption,
  weekday routines, day isolation, persistence and 320–1440px layouts.
- `python scripts/browser_voice.py --url http://127.0.0.1:8017`: PASS.
  Simulated recognition, intercepted inference, empty-day setup, pending-task
  Gemini dispatch, tool trace display, speech lifecycle and permission errors.
- `python scripts/browser_upgrades.py --url http://127.0.0.1:8017`: PASS.
  MCP task/calendar review links, UI-only confirmation, deterministic typed
  planning, expanded tool trace, preference save/forget/reload, trace clearing
  across dates and 320–1440px layouts including expanded proposal details.

Browser screenshots are in ignored `data/upgrades/` and `data/personal-days/`.
A physical microphone and actual remote speech-recognition service were not
tested. The verification server used an isolated SQLite database and was stopped
after testing.

## Scope and safeguards

- MCP Streamable HTTP implements JSON responses for POST, initialization,
  notification acknowledgement, ping, tools/list and tools/call. GET streams and
  DELETE termination return the spec-permitted 405. Tests cover headers, origins,
  malformed requests, session selectors, concurrent drafts and COMMIT rejection.
- MCP and Gemini expose READ/PROPOSE plus an explicit PREFERENCE tier. Preference
  writes affect only memory and state version. Tasks and calendar change only
  through UI confirmation.
- Scheduling preserves full task duration. Primary hours remain 09:00–17:00;
  long work can split into chunks of at least 30 minutes before evening overflow,
  with a maximum flexible-work bound of 21:00 and hard deadlines.
- Partial updates preserve omitted/null priority and category; explicit deadline
  null clears the deadline. Protected work stays immutable.
- UTF-8 scanning covers source, tests, scripts, skills and public documents.
  The named UI glyphs were already clean when this session began.
- The empty root `flowpilot.db` was verified as zero bytes and removed.
  OpenAPI and generated TypeScript are synchronized.
- The local MCP server and Agent Skill are implemented. Remote Alexa+ account
  onboarding, OAuth, external calendar sync, deployment and certification have
  not been performed. This remains a local single-user prototype.
- The final pass includes the loading text, initial speech guard, interim speech
  fallback, repeat-confirm rollback, partial-update inheritance and Gemini SDK
  dependency. Draft tests cover pending lookup, atomic rollback, idempotency,
  cancellation, session isolation and mocked clarification-to-draft tool calls.
- The three named internal root prompts/audits are removed. Local repository
  dumps are ignored, and existing application changes are included in the
  submission commit. Publication follows the successful verification gates.
  Video upload and final Devpost submission remain entrant actions.
