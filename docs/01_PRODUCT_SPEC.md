# FlowPilot — Product Specification

## Pitch

**FlowPilot** is an ambient AI scheduling agent that turns messy tasks and constraints into a concrete time-block plan, and when life interrupts, instantly replans around what already happened.

- **Target user:** A busy professional juggling deadlines, meetings, and shifting priorities.
- **Pain point:** After an interruption, you waste 10–20 minutes re-deciding what to do next. Existing planners show a list; FlowPilot shows a *time-committed schedule* and adapts it live.
- **Why ambient/multimodal:** Planning happens in the cracks — between meetings, while cooking, during commute. An always-visible schedule surface with voice-ready interaction beats a tab you have to open and manually edit.

## Surface Design (Echo-Show-Style)

The UI is a single-page ambient display, not a chat transcript.

| Element | Behavior |
|---|---|
| **Utterance bar** | Text input (first-class). Voice input and TTS are P1. |
| **Response line** | Short spoken-style agent response (1–2 sentences). |
| **Plan Preview card** | Shows the schedule diff: kept ✓, moved →, shortened ↓, dropped ✗. Appears when PROPOSE tools complete. |
| **Schedule timeline** | Vertical time-block view of the committed schedule. Color-coded by category. Shows completed blocks as immutable (greyed/checked). |
| **Confirm / Cancel** | Primary action button pair. Confirm triggers COMMIT. Cancel discards the proposal. |
| **Tool trace** | Collapsible panel showing tools invoked, arguments, results. Sourced from persisted execution log. |
| **Mode badge** | Always visible: "Live model" or "Deterministic demo mode". Never hidden. |
| **Memory indicator** | "Remembered: [summary]" pill appears when cross-session memory is retrieved or stored. |

## Golden Demo Scenario

> This is the primary product contract. The deterministic provider, seed data, smoke test and video all execute this exact scenario.

### Seed State (defined in `server/seed.json`, referenced by tests and reset)

Demo timestamp: **2026-10-22 09:00 IST (Wednesday)**

**Existing tasks:**
| ID | Title | Duration | Deadline | Priority | Category | Status |
|---|---|---|---|---|---|---|
| T1 | Quarterly report draft | 2h | Oct 22 17:00 | HIGH | work | pending |
| T2 | Review PR #247 | 45min | Oct 22 14:00 | MEDIUM | work | pending |
| T3 | Grocery shopping | 1h | Oct 22 20:00 | LOW | personal | pending |
| T4 | Team standup | 30min | — | HIGH | meeting | pending |
| T5 | Gym session | 1h | — | MEDIUM | personal | pending |

**Existing calendar blocks:**
| Start | End | Title | Immutable |
|---|---|---|---|
| 10:00 | 10:30 | Team standup (T4) | yes |
| 13:00 | 14:00 | Lunch | yes |

**No prior memory entries.**

### Turn 1: Initial Planning

- **Utterance:** "Plan my day — I need to finish the quarterly report by 5 PM and review that PR before the 2 PM meeting."
- **Agent reads:** `get_tasks`, `get_calendar`, `get_current_time`
- **Agent proposes:** `propose_schedule` with time blocks:
  - 09:00–09:05: Planning (overhead)
  - 09:05–10:00: Quarterly report draft (part 1, 55 min)
  - 10:00–10:30: Team standup (immutable)
  - 10:30–11:15: Review PR #247 (45 min, before 14:00 deadline)
  - 11:15–12:15: Quarterly report draft (part 2, 60 min)
  - 12:15–13:00: Gym session (shortened to 45 min)
  - 13:00–14:00: Lunch (immutable)
  - 14:00–14:45: Quarterly report draft (part 3, 45 min — completes 2h total)
  - 15:00–16:00: Grocery shopping
  - 16:00–17:00: Buffer / overflow
- **Plan state:** `PROPOSED`
- **UI:** Plan Preview card appears showing the proposed schedule. Confirm/Cancel visible.
- **Response line:** "Here's your day — I've split the report into three blocks to hit your 5 PM deadline and scheduled the PR review before 2 PM."

### Approval

- **User clicks Confirm.**
- **Agent executes:** `commit_schedule` — all blocks written to DB atomically.
- **Plan state:** `PROPOSED → CONFIRMED → EXECUTING → EXECUTED`
- **DB mutations:** Schedule blocks inserted, task statuses updated to `scheduled`.
- **Memory written:** `{ "key": "work_style", "value": "User prefers morning focus blocks for reports", "session": "demo-session-1" }`
- **UI:** Timeline updates. Plan Preview card collapses. "Remembered: User prefers morning focus blocks" pill appears.

### Turn 2: Interruption and Replan

Simulated time advance to **11:30 IST**. Standup and PR review are completed. Report part 1 done. Part 2 is in progress.

- **Utterance:** "My manager just scheduled a 1-on-1 at 2 PM for 30 minutes — replan around it."
- **Agent reads:** `get_schedule`, `get_current_time` (11:30)
- **Agent marks:** standup and PR review blocks as `COMPLETED` (immutable). Report part 1 as `COMPLETED`.
- **Agent proposes:** `propose_replan` with diff:
  - ✓ Kept: 09:05–10:00 report pt 1, 10:00–10:30 standup, 10:30–11:15 PR review (all COMPLETED)
  - ✓ Kept: 11:15–12:15 report pt 2 (in progress)
  - ✓ Kept: 12:15–13:00 gym, 13:00–14:00 lunch
  - → Moved: report pt 3 from 14:00 → 14:30 (after 1-on-1)
  - **New:** 14:00–14:30 Manager 1-on-1
  - → Moved: grocery from 15:00 → 15:15
  - ↓ Shortened: buffer from 60 min → 45 min
  - Trade-off: "Report still finishes by 5 PM. Grocery pushed 15 min. Buffer shortened."
- **Plan state:** `PROPOSED`
- **UI:** Plan Preview card shows diff with kept/moved/shortened markers. Completed blocks are greyed and immutable.

### Approval of Replan

- **User clicks Confirm.**
- **Plan state:** `EXECUTED`
- **DB:** New blocks written, old non-completed blocks updated. Completed blocks untouched.
- **Memory written:** `{ "key": "manager_meeting", "value": "Manager 1-on-1 typically 30 min, schedule for unexpected", "session": "demo-session-1" }`

### Turn 3: Session Restore (after page reload)

- **User reloads the page.**
- **Agent reads:** `get_schedule`, `get_memory`
- **UI:** Timeline renders the current committed schedule. Memory indicator shows "Remembered: morning focus blocks, manager meetings".
- **Utterance:** "What's left for today?"
- **Response:** "You have report part 3 at 2:30 PM after your 1-on-1, then grocery shopping at 3:15. Buffer until 5."
- **Memory used in response:** references the stored preference.

### Expected Failure & Fallback

- If the live Gemini provider times out during Turn 1, the system falls back to the deterministic provider with `degraded: true`. The mode badge changes to "Deterministic demo mode (fallback)". The response and plan are still valid because deterministic mode runs real tools against real DB state.

## Live-LLM Acceptance Invariants

When running with a live provider, exact wording varies. These invariants must hold:

1. No time-block overlaps in any proposed or committed schedule.
2. Completed blocks are never moved, shortened or deleted.
3. Deadline-critical tasks (T1 by 17:00, T2 by 14:00) are scheduled before their deadlines.
4. Total scheduled duration per task matches or exceeds the task's required duration.
5. Immutable calendar blocks are preserved.
6. Plan state transitions follow the state machine (02 §4.5).
7. `state_version` increments on every domain mutation.

## Scope Tiers

### P0 (golden demo + mandatory submission)
- Deterministic provider with full golden demo scenario
- Live Gemini provider with invariant-based acceptance
- All 5 tool types (get_tasks, get_calendar, get_current_time, propose_schedule/replan, commit_schedule)
- Plan state machine with idempotent confirm
- Session isolation and seed/reset
- Stale-plan protection (409 on version mismatch)
- Schedule diff display (kept/moved/shortened/dropped)
- Cross-session memory (write on commit, read on session start)
- Provider fallback with mode badge
- Tool trace (collapsible)
- `contract:check` command
- Source repo, demo video ≤170s, testing instructions, product feedback, README

### P1 (polish, after all P0 BUILD done)
- Voice input (Web Speech API) and TTS output
- MCP server (Streamable HTTP, same tool registry)
- Hosted deployment (unless rules require it, then P0)
- Playwright smoke test
- UI animations and responsive polish
- Additional tool depth (task creation, calendar sync)

### P2 (optional, forbidden after freeze)
- OpenAI provider adapter
- AWS service adapter (only if free)

### Anti-scope
- OAuth / real authentication
- Multi-tenant cloud database
- Mobile native wrappers
- Paid SaaS integrations
- Real calendar API integration (Google Calendar, Outlook)
