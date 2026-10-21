# FlowPilot — Debug Audit & Release Readiness Ledger

**Last Updated:** 2026-10-22 01:08 IST  
**Hackathon:** Build, Ship, Shape: Amazon Developer Hackathon 2026 (Alexa+ Track)  
**Submission Deadline:** October 24, 2026, 12:30 AM IST (~47 hours remaining)  
**Coordinator:** Gemini Flash 3.8 High (Antigravity IDE)  
**Executor:** Codex (Direct CLI integration verified) / Gemini

---

## 1. Release Dashboard

| Metric | Status |
|---|---|
| **Current Release Status** | **GREEN** (All P0 BUILD tasks complete; critical JSON parsing bug resolved; defensive API client active; 134/134 tests passing) |
| **Confirmed Blockers Remaining** | 0 |
| **High-Severity Issues Remaining** | 0 |
| **Automated Checks** | 134/134 pytest passing; `npm run smoke` passing; `npm run contract:check` passing; `python scripts/check_docs.py` passing |
| **Golden Demo Scenario Results** | Turn 1 (Plan) ✓, Confirm 1 ✓, Turn 2 (Replan) ✓, Confirm 2 ✓, Turn 3 (Query) ✓ (Both offline deterministic and live model supported) |
| **Submission Blockers** | 0 architectural; requires demo rehearsal video (TASK-024/025) and Devpost form submission (TASK-026) |
| **Last Verified Git Commit** | `f5ba6f8` (New commit pending) |
| **Next Action** | Commit verified fixes, rebuild frontend distribution, and perform final submission readiness walk-through |

---

## 2. Defect Ledger

### BUG-001: Frontend Crashes with `Unexpected token 'I', "Internal S"... is not valid JSON` on Server Error

- **BUG ID:** BUG-001
- **Severity:** BLOCKER
- **Affected Component:** `frontend/src/api/client.ts` & `server/main.py`
- **Reproduction Procedure:**
  1. Trigger any HTTP 500 or non-JSON error response (e.g. backend restart, network gateway error, or unhandled server exception).
  2. `client.ts` executes `const data = await response.json()` unconditionally before evaluating `response.ok` or inspecting `Content-Type`.
- **Actual Behavior:**
  - Browser console and UI alert throw `SyntaxError: Unexpected token 'I', "Internal S"... is not valid JSON`.
  - Application displays a raw, broken JSON parse alert.
- **Expected Behavior:**
  - Server consistently returns structured JSON error envelopes (`{"error": {"code": "...", "message": "..."}}`) even for unexpected 500 exceptions.
  - Frontend client safely inspects `response.ok` and `Content-Type`, falls back to text parsing, and surfaces a clean, user-friendly error without crashing or throwing `SyntaxError`.
- **Root Cause:**
  1. In `frontend/src/api/client.ts`, `request()` called `await response.json()` unconditionally before checking `response.ok`. When a server returns plain text `"Internal Server Error"`, `JSON.parse` crashes on the `'I'`.
  2. In `server/main.py`, FastAPI lacked global exception handlers for `Exception`, `StarletteHTTPException`, and `RequestValidationError`, allowing Starlette to fall back to plain-text `text/plain` 500 responses.
- **Responsible Agent:** Gemini
- **Repair Status:** RESOLVED
- **Fix Details:**
  1. Updated `frontend/src/api/client.ts` with defensive `request()`: network error handling, content-type inspection, safe `response.json()` try/catch, plain-text fallback, and structured `ApiError` formatting.
  2. Added global exception handlers in `server/main.py` for `RequestValidationError` (422), `StarletteHTTPException`, and unhandled `Exception` (500) to ensure uniform JSON ErrorEnvelope responses.
- **Regression Test:** `tests/test_api_errors.py::test_validation_error_envelope` and `test_404_error_envelope`
- **Verification Result:** PASSED (All tests in `test_api_errors.py` pass; `npm test` passes 134/134)
- **Relevant Commit:** Pending commit

---

### BUG-002: Live Gemini Model Proposal Validation Rejects Valid Schedules with Identity Tuple Mismatch

- **BUG ID:** BUG-002
- **Severity:** HIGH
- **Affected Component:** `server/engine/validator.py` & `server/tools/registry.py`
- **Reproduction Procedure:**
  1. Set provider to `gemini` with `GEMINI_API_KEY`.
  2. Submit "Plan my day".
  3. Model calls `propose_schedule` with blocks containing "Team standup" and "Lunch" without database UUID `id`.
- **Actual Behavior:**
  - `validator.py` compares `_identity(new) == _identity(old)`.
  - `old` has `id` (UUID string), so `_identity(old)` is a string.
  - `new` lacks `id` (as schema rejected `id`), so `_identity(new)` is a tuple `(task_id, title)`.
  - String never equals tuple, causing `matches` to be empty and raising `ValueError: Protected completed/immutable block modified or removed: Team standup`.
  - Model repair fails and raises an unhandled exception.
- **Expected Behavior:**
  - Validator recognizes protected blocks by title, task ID, or persistent ID.
  - Schema allows `id` optionally so if provided it is accepted.
  - Valid LLM-generated schedules pass proposal validation.
- **Root Cause:**
  - Asymmetry between database block dictionary structure and LLM tool parameter schema, coupled with rigid `_identity` comparison.
- **Responsible Agent:** Gemini
- **Repair Status:** RESOLVED
- **Fix Details:**
  1. Updated `server/engine/validator.py` to match protected blocks across title, task ID, or persistent ID, verifying that start time, end time, and title match.
  2. Updated `_proposal_schema` in `server/tools/registry.py` to allow optional `"id"` property.
- **Regression Test:** `tests/test_api_errors.py::test_validator_immutable_blocks_matching_by_title` and `test_validator_immutable_blocks_rejects_moved_protected_block`
- **Verification Result:** PASSED (Both regression tests pass; smoke tests pass)
- **Relevant Commit:** Pending commit
