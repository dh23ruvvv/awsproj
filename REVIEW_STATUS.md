# Code review checkpoint

This repository contains the current FlowPilot implementation for review, including work in progress on voice input and Gemini task-change drafts.

## Verified at this checkpoint

- Frontend production build: passed.
- OpenAPI / generated TypeScript contract: passed.
- Backend tests: 206 passed, 2 live-provider tests skipped.
- Earlier personal-day browser checks passed guided planning, named interruptions, weekday routines, persistence and responsive widths before the latest voice integration.

## Review priorities

1. Review the new VoiceInput lifecycle, recognition errors, transcript handling, auto-send and spoken reply behavior. Real microphone recognition has not been validated end to end.
2. Review task-draft ownership, validation, atomic confirmation, cancellation, version checks and repeat-confirm behavior. Dedicated regression coverage for the newest draft flow is still needed.
3. Validate Gemini task-change function calling and clarification history with mocked responses and an explicitly authorized live request. No live Gemini request was run for this checkpoint.
4. Re-run the personal-day browser checks against a restarted backend containing the latest schema and routes.
5. Preserve explicit human approval for task drafts and calendar changes. Never treat recognition text as approval.

## Run and tests

Follow README.md for installation. Build and start from the repository root:

```powershell
npm.cmd --prefix frontend run build
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Checks:

```powershell
python -m pytest tests/ -q -p no:cacheprovider --basetemp .test-tmp-review
npm.cmd run contract:check
python scripts/browser_personal_days.py --url http://127.0.0.1:8000
```

Environment files, API credentials, local SQLite databases and generated frontend build files are excluded from Git. Configure your own .env from .env.example. The previous release notes describe earlier checkpoints; this file states the limits of the current review snapshot.
