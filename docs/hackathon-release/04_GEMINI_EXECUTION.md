# FlowPilot Gemini Execution Plan — Frontend, Explainability, and Alexa+ Experience

> **Purpose:** Detailed implementation guide for Gemini (frontend, UX, and product lead) mapping 1:1 to canonical tasks TASK-201 through TASK-205. Covers frozen API contracts, comprehensive UI state handling, diff visualization, and accessibility standards.  
> **Last verified against commit:** `f2f2706`  
> **Status Legend:**  
> - `[VERIFIED]`: Confirmed directly in active repository source code, git history, or live environment.  
> - `[INFERRED]`: Reasoned from configuration and hackathon rules; pending execution.  
> - `[NOT RUN]`: Explicitly unexecuted in the current session.  
> - `[P0]`: Critical priority — required for shippable MVS and demo integrity.  
> - `[P1]`: High priority — completeness, polish, and error prevention.  

---

## 1. Operating Rules for Gemini Executor

1. **Gate Precondition (CONTRACT-FREEZE):** Gemini begins frontend implementation **ONLY AFTER** Codex reaches **GATE-2 (CONTRACT-FREEZE)** and `generated/openapi.json` is committed.
2. **Strict Scope Boundary:** Touch ONLY frontend components, styles, types, and client docs (`frontend/src/`, `frontend/package.json`). Never edit Python backend files (`server/`, `tests/`).
3. **No Invented Endpoints:** Use strictly the frozen endpoints exposed by `server/main.py` and typed in `frontend/src/api/types.ts`.
4. **Commit Convention:** Every commit must reference the task ID in its header:
   - Format: `feat(TASK-xxx): <imperative summary>` or `fix(TASK-xxx): <imperative summary>`.
5. **No Secret Access:** Never read or commit secrets or environment variable files.

---

## 2. Frozen Backend API Contracts (React Client Reference)

All endpoints reside under `/api/v1` and return JSON. The client must handle these exact request and response shapes:

### 2.1 Agent Utterance (`POST /api/v1/sessions/{sid}/agent/message`)
- **Request Body:**
  ```json
  {
    "message": "Plan my day",
    "state_version": 1
  }
  ```
- **Success Response (200 OK):**
  ```json
  {
    "response": "Here is your optimized schedule for today...",
    "plan_id": "c7a8b3d1-4e9f-4a0b-8d3e-1f2a3b4c5d6e",
    "has_proposal": true,
    "state_version": 1,
    "provider_used": "gemini",
    "degraded": false,
    "tool_trace": [
      {
        "tool": "get_tasks",
        "args": {},
        "result_summary": "[...]",
        "duration_ms": 12
      }
    ]
  }
  ```
- **Error Response (409 Conflict):**
  ```json
  {
    "error": {
      "code": "STALE_STATE_VERSION",
      "message": "Client state version 1 does not match current session version 2"
    }
  }
  ```

### 2.2 Plan Details (`GET /api/v1/sessions/{sid}/plans/{pid}`)
- **Success Response (200 OK):**
  ```json
  {
    "plan_id": "c7a8b3d1-4e9f-4a0b-8d3e-1f2a3b4c5d6e",
    "session_id": "...",
    "status": "PROPOSED",
    "proposed_blocks": [...],
    "diff": {
      "kept": [{"block_id": "...", "title": "Team Standup"}],
      "moved": [{"block_id": "...", "title": "Deep Work", "old_start": "...", "new_start": "..."}],
      "shortened": [{"block_id": "...", "title": "Buffer", "old_duration_min": 60, "new_duration_min": 15}],
      "lengthened": [{"block_id": "...", "title": "Review", "old_duration_min": 30, "new_duration_min": 60}],
      "dropped": [],
      "added": [{"title": "Client Sync", "start_time": "...", "end_time": "..."}]
    },
    "explanation": "Shifted Deep Work to 14:00 to accommodate client sync.",
    "state_version": 1
  }
  ```

### 2.3 Confirm Plan (`POST /api/v1/sessions/{sid}/plans/{pid}/confirm`)
- **Request Body:**
  ```json
  {
    "state_version": 1
  }
  ```
- **Success Response (200 OK):**
  ```json
  {
    "committed": true,
    "state_version": 2,
    "execution_log": [...]
  }
  ```
- **Stale Error Response (409 Conflict):**
  ```json
  {
    "error": {
      "code": "STALE_PLAN",
      "message": "Plan state_version does not match current session state."
    }
  }
  ```

### 2.4 Cancel Plan (`POST /api/v1/sessions/{sid}/plans/{pid}/cancel`)
- **Success Response (200 OK):**
  ```json
  {
    "cancelled": true,
    "state_version": 1
  }
  ```

---

## 3. Ordered Gemini Implementation Specifications

---

### [TASK-201] Generate Frontend Types from Frozen Schema
- **Specification Reference:** See [TASK-201 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-201-generate-frontend-types-from-frozen-schema).
- **Target File:** `frontend/src/api/types.ts`.
- **Preconditions:** GATE-2 passed; `generated/openapi.json` committed.
- **Execution Instructions:**
  1. Run OpenAPI type generator:
     ```powershell
     npm --prefix frontend run typegen
     ```
  2. Verify that `DiffSummary` in `types.ts` contains `lengthened`.
  3. Compile TypeScript to confirm zero type errors:
     ```powershell
     npx --prefix frontend tsc --noEmit
     ```
- **Checkpoint Command:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Commit Message:** `chore(TASK-201): synchronize typescript types from frozen openapi schema`

---

### [TASK-202] Render Lengthened Duration Badges in PlanPreview (FLAW-005)
- **Specification Reference:** See [TASK-202 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-202-render-lengthened-duration-badges-in-planpreview).
- **Target Files:** `frontend/src/components/PlanPreview.tsx`, `frontend/src/components/PlanPreview.css`.
- **Implementation Instructions:**
  1. In `PlanPreview.tsx`, update `DiffSummary` interface to include `lengthened?: DiffItemLengthened[]`.
  2. Add render block for `diff.lengthened`:
     - Render badge `<span className="plan-preview-badge lengthened-badge">Lengthened</span>`.
     - Display duration transition: `item.title: {item.old_duration_min}m → {item.new_duration_min}m`.
  3. In `PlanPreview.css`:
     - Style `.lengthened-badge` with a high-contrast teal/cyan badge (`background: #0e7490; color: #ecfeff; border: 1px solid #22d3ee;`).
     - Ensure mobile responsiveness for small modals.
- **Checkpoint Command:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Commit Message:** `feat(TASK-202): render lengthened duration badges in plan preview diff modal`

---

### [TASK-203] Stale-State and Double-Approve Defense in UI (NEW-002)
- **Specification Reference:** See [TASK-203 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-203-stale-state-and-double-approve-defense-in-ui).
- **Target File:** `frontend/src/App.tsx`.
- **Implementation Instructions:**
  1. In `handleConfirmPlan`, introduce immediate debouncing:
     - Set a local boolean `isConfirming` immediately on click.
     - Close the `activePlan` modal or disable both buttons instantly to prevent repeated clicks.
  2. Implement dedicated error handling for HTTP 409 responses:
     - If the API returns code `STALE_PLAN` or `STALE_STATE_VERSION`:
       - Clear `activePlan` so the stale modal does not trap the user.
       - Set `agentResponse` to: *"Your schedule was updated since this plan was proposed. Please ask FlowPilot to refresh your day plan."*
  3. Add a visual banner above the chat timeline alerting the user when their local state has drifted.
- **Checkpoint Command:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Commit Message:** `fix(TASK-203): prevent double-approve races and handle 409 stale plan gracefully in UI`

---

### [TASK-204] Alexa+ Ambient Feedback & Interaction Polish
- **Specification Reference:** See [TASK-204 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-204-alexa-ambient-feedback--interaction-polish).
- **Target Files:** `frontend/src/components/UtteranceBar.tsx`, `frontend/src/App.tsx`.
- **Implementation Instructions:**
  1. In `UtteranceBar.tsx`, add an interactive demo chip bar above the text input:
     - Chip 1: `"📅 Plan my day"` -> populates input and triggers submission.
     - Chip 2: `"⚡ Emergency client sync at 2 PM"` -> triggers interruption replan turn.
     - Chip 3: `"📋 What tasks are left?"` -> triggers status inspection turn.
  2. When `loading === true`, display an ambient Alexa+ pulsing glow around the header and utterance bar in hex `#00CAFF` (Alexa cyan).
  3. Update `ModeBadge.tsx` to clearly indicate:
     - Live Mode: `"Alexa+ Ambient Agent (Gemini 2.5 Flash)"`
     - Degraded/Offline Mode: `"Alexa+ Fallback Mode (Deterministic)"`
- **Checkpoint Command:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Commit Message:** `feat(TASK-204): add Alexa+ ambient glow, mode badge, and quick demo utterance chips`

---

### [TASK-205] Accessibility & Keyboard Navigation Hardening
- **Specification Reference:** See [TASK-205 in 02_ORDERED_TASK_GRAPH.md](file:///D:/Projects/AWS%20Hackathon/docs/hackathon-release/02_ORDERED_TASK_GRAPH.md#task-205-accessibility--keyboard-navigation-hardening).
- **Target Files:** `frontend/src/components/PlanPreview.tsx`, `frontend/src/components/TaskList.tsx`.
- **Implementation Instructions:**
  1. In `PlanPreview.tsx`:
     - Add `role="dialog"` and `aria-modal="true"` to modal overlay.
     - Attach `keydown` listener to dismiss modal on `Escape` key (`onCancel()`).
     - Trap focus inside the dialog while open.
  2. In `ResponseLine.tsx` / `App.tsx`:
     - Add `aria-live="polite"` to agent response container so screen readers announce incoming proposals.
  3. Verify color contrast across all diff badges:
     - Kept (gray), Moved (blue), Shortened (amber), Lengthened (teal), Added (green), Dropped (red). Ensure all text meets WCAG AA 4.5:1 ratio against background.
- **Checkpoint Command:**
  ```powershell
  npm --prefix frontend run build
  ```
- **Commit Message:** `feat(TASK-205): improve accessibility with modal focus trap, escape key, and aria-live announcements`

---

## 4. UI State Matrix & Visual Requirements

The frontend must present distinct, clear UI states without ambiguity or silent failures:

| State | Trigger | Visual Presentation | User Action Required |
|---|---|---|---|
| **Idle** | Default on session load | Full timeline with committed blocks; task sidebar with pending tasks; active prompt bar. | User types instruction or clicks demo chip. |
| **Listening / Processing** | Utterance submitted (`loading=true`) | Pulsing Alexa+ ambient cyan ring; disabled input bar; subtle skeleton shimmer. | None (wait for agent response). |
| **Proposal Pending** | Agent returns `has_proposal=true` | `PlanPreview` modal appears; diff badges rendered (`Kept`, `Moved`, `Shortened`, `Lengthened`, `Added`, `Dropped`); explanation card. | User reviews before/after diff and clicks **Confirm** or **Cancel**. |
| **Proposal Confirmed** | User clicks Confirm | Modal closes; timeline updates with animation; agent response announces success; state version counter increments. | None (user continues workday). |
| **Stale State (409)** | Concurrent action / stale client version | Orange warning banner: *"Schedule updated elsewhere. Please ask FlowPilot to refresh."* Modal dismissed. | User asks FlowPilot to plan or replan. |
| **Degraded / Fallback** | Circuit breaker tripped (2 Gemini errors) | Yellow pill badge: `"Alexa+ Fallback Mode (Deterministic)"`; informational banner explaining live API is temporarily paused. | User continues normally using deterministic engine. |
| **Validation Error** | Task exceeds day or overlaps | Red inline alert explaining scheduling constraint; timeline unchanged. | User adjusts requested task duration or deadline. |

---

## 5. Gemini Checkpoint & Verification Commands

```powershell
# Type generation from frozen backend schema:
npm --prefix frontend run typegen

# Typecheck and production bundle build:
npm --prefix frontend run build

# Start local frontend dev server for manual UI inspection:
npm --prefix frontend run dev
```
