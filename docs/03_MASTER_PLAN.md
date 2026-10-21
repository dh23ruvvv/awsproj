# FlowPilot — Master Plan

> Backwards schedule. Full scope profile (R ≈ 52h).

## Timeline

**Deadline:** Oct 24, 2026 00:30 IST (T-0)
**Planning complete:** Oct 21, 2026 ~21:00 IST (T-51.5h)

| T-minus | IST Time | Milestone / Event |
|---|---|---|
| T-51h | Oct 21, 21:30 | Planning complete. Gemini starts TASK-001 (Codex preflight) |
| T-48h | Oct 22, 00:30 | M1 target: walking skeleton (TASK-004 through TASK-012) |
| T-40h | Oct 22, 08:30 | **Human checkpoint:** TASK-002 (API key), TASK-003 (Devpost rules) |
| T-36h | Oct 22, 12:30 | M2 target: full golden path (TASK-013 through TASK-019) |
| T-30h | Oct 22, 18:30 | **Mid-point checkpoint.** If M2 not done, trigger cut-down ladder. |
| T-24h | Oct 23, 00:30 | M3 target: live Gemini provider + security tests (TASK-015, TASK-021) |
| T-20h | Oct 23, 04:30 | Golden smoke test passes (TASK-020). README updated (TASK-023). |
| T-16h | Oct 23, 08:30 | Early demo rehearsal (TASK-024). |
| T-12h | Oct 23, 12:30 | P1 window opens (if all P0 BUILD done). |
| T-8h | Oct 23, 16:30 | **HARD FEATURE FREEZE.** No new code after this. |
| T-6h | Oct 23, 18:30 | Pre-submission audit (TASK-027). Fix any findings. |
| T-4h | Oct 23, 20:30 | Final video recording (TASK-025). |
| T-3h | Oct 23, 21:30 | **SUBMISSION-READY LINE.** Video uploaded, all materials ready. |
| T-2h | Oct 23, 22:30 | Devpost submission (TASK-026). |
| T-1h | Oct 23, 23:30 | Verification buffer. Check links, re-read submission in incognito. |
| T-0 | Oct 24, 00:30 | **DEADLINE.** |

## Milestones

### M1: Walking Skeleton (target: T-48h)
TASK-001, TASK-004, TASK-005, TASK-006, TASK-007, TASK-008, TASK-009, TASK-010, TASK-011, TASK-012
- Complete loop: utterance → API → tools → SQLite → approval → state mutation → UI placeholder
- Deterministic provider only
- Git tag: `m1-slice`

### M2: Full Golden Path (target: T-36h)
TASK-013, TASK-014, TASK-016, TASK-017, TASK-018, TASK-019
- All UI components wired
- Full golden demo scenario on deterministic
- Contract check passing
- Git tag: `m2-golden`

### M3: Live Provider + Hardening (target: T-24h)
TASK-015, TASK-020, TASK-021
- Gemini provider with fallback
- Golden smoke test
- Security tests (injection, idempotency, stale-plan)
- Git tag: `m3-live`

### M4: Submission Pathway (parallel from M2 end)
TASK-022, TASK-023, TASK-024, TASK-025, TASK-026, TASK-027
- Dev scripts, README, rehearsal, final video, audit, submission

### M5: P1 (T-12h to T-8h, only if all P0 BUILD done)
TASK-P1-001 through P1-004
- Voice, TTS, MCP, UI polish
- Each must pass full P0 smoke test to merge

### M6: Freeze + Submit (T-8h to T-0)
No new features. Only bug fixes, video, submission.

## Minimum Valid Submission Pathway (MVSP)

Achievable from M1 + M2 alone:
- Working app with deterministic provider (golden demo scenario)
- Schedule display, plan preview with diff, confirm/cancel
- Source repo with README and testing instructions
- Demo video showing deterministic mode (honestly stated)
- Devpost submission with all mandatory fields

MVSP does **not** require: live Gemini, voice/TTS, MCP, hosted deployment, UI animations.

## Emergency Cut-Down Ladder

If behind at T-30h checkpoint, cut in this order (each preserves track eligibility):

1. **Hosted deployment** → run locally, video shows localhost
2. **Voice & TTS** → typed input only
3. **MCP server** → approach B only (simulation), honestly stated
4. **Live provider** → deterministic only, honestly disclosed as rule-based demo mode
5. **UI polish** → functional but unstyled, retain core golden-path replan flow

Never cut: the replan capability, the deterministic golden demo, the video, or the submission materials.

## P0 Sizing

- P0 BUILD tasks: ~17 tasks × ~40 min avg = ~11h execution time
- P0 SUBMIT tasks: ~6 tasks = ~4h (parallel with late BUILD tasks)
- P0 target completion: ~45% of R = T-28.5h (Oct 22, 20:00 IST)
- Slack: ~4h before freeze
