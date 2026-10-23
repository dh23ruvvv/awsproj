# FlowPilot submission draft

Status: ready-to-edit copy and checklist only. This file does not submit a project, verify entrant eligibility, publish a repository, or upload a video.

## Verified rules reference

Checked October 22, 2026: [official competition rules](https://amazonappdev2026.devpost.com/rules). The submission deadline is October 23 at 12:00 PM PDT (October 24 at 00:30 IST). Alexa+ explicitly permits a web simulation using the entrant's chosen AI/agentic tools; this alternative needs no particular SDK or MCP interface. The simulation source and working demonstration are still required. Organizer decisions govern eligibility.

Provide GitHub code, assets and setup instructions: either a public repository with a detectable open-source license, or private access shared as instructed in the rules. Supply an English description, track selection, product feedback and a publicly visible YouTube/Vimeo demonstration shorter than three minutes. Include testing credentials if access requires them. Complete final submission before the deadline; a draft is insufficient. Review the rules' entrant, ownership and access conditions personally. [Source](https://amazonappdev2026.devpost.com/rules)

## Suggested project fields

**Name:** FlowPilot

**Tagline:** A day planner that adapts with you—and waits for your approval.

**Primary track:** Alexa+ — simulated web experience.

**Mini-challenges:** None claimed. Add a category only after independently documenting qualifying work.

**Repository URL:** [USER: insert accessible GitHub URL]

**Demo video:** [USER: insert public YouTube or Vimeo URL]

**Hosted app:** [USER: insert only if actually deployed and tested; local setup is documented in README]

**Testing credentials:** Local demonstration needs no account. [USER: describe any credentials required by your actual hosted setup; never include API secrets.]

## Project description

### Inspiration

A busy day rarely follows its first plan. Meetings appear, tasks compete for time, and a helpful assistant should explain the consequences before changing someone's commitments. We built FlowPilot around that moment of decision.

### What it does

FlowPilot is an Alexa+-inspired day-planning simulation in a web app. Users maintain tasks with durations, priorities and deadlines, request a schedule, and introduce an interruption with explicit times. The backend fits work around protected calendar commitments. The interface compares proposed and saved schedules so users can inspect added, moved, unchanged, removed or duration-changed blocks when present.

A proposal does not change the calendar. Confirm persists the reviewed plan; Cancel leaves the saved schedule alone. Session recovery retrieves committed state after refresh. When full work cannot fit, the offline scheduler returns a recoverable explanation instead of silently shortening tasks.

### How we built it

The interface uses React, TypeScript and Vite. A Python FastAPI service orchestrates read tools, proposal validation and separate approval/commit tools. SQLite stores tasks, calendar blocks, proposals and execution records. The deterministic provider supports a reproducible offline demonstration using real scheduling and persistence. An optional Gemini provider exists for model-driven tool calling; it requires configuration and may fall back to the labeled offline mode.

There is no official Alexa+ SDK integration, Alexa account connection, external calendar synchronization, deployed AWS service, Ring integration or Bee integration in this demonstration. The recorded mode must be stated accurately. Live Gemini success has not been established by this submission draft.

### Engineering choices and challenges

We prioritized full task duration, preserved block identity and protected commitments over a rigid demo timetable. Proposal comparison and version checks keep review separate from execution. The deterministic path intentionally supports a narrow set of requests; custom task data enters through explicit task controls. That limitation makes the offline demonstration understandable and reproducible.

### Customer impact

FlowPilot is intended for people juggling focused work and fixed appointments. Its central benefit is the ability to understand a schedule change before accepting it. This is a prototype benefit statement, not a claim of measured productivity gains or deployed customers.

### Next steps

Evaluate planning quality with users; improve natural-language coverage and task splitting; add configurable availability and stronger multi-day planning; investigate authorized external calendar integration. These are future work, not implemented submission features.

### Development-period disclosure

[USER: state when this project started. If it predates the event, list the substantial features implemented during the event and demonstrate those changes. Include your own role and collaborator credits accurately.]

## Product feedback worksheet

Complete this for tools actually used. Explain purpose, strengths, shortcomings, onboarding experience, and whether you would use each again with reasons. [Feedback requirements](https://amazonappdev2026.devpost.com/rules)

| Tool | Actual role | Entrant feedback to complete |
| --- | --- | --- |
| React / TypeScript / Vite | Browser interface and build tooling | [Setup experience; useful behavior; concrete issues; repeat-use decision] |
| FastAPI / Pydantic | HTTP API and request validation | [Observed strengths, limitations and onboarding] |
| SQLite | Local persistent session and proposal data | [Transaction experience, limitations and repeat-use decision] |
| pytest / HTTP test client | Automated backend verification | [Testing workflow and any observed friction] |
| Gemini SDK/API | Optional provider only | [Include actual usage and verified observations; say untested if not exercised] |
| Development assistants/tools | [USER: identify tools actually used] | [Describe assistance honestly; do not invent AWS or Kiro usage] |

No Alexa+ SDK onboarding experience is claimed. This project uses the simulation route. Do not turn anticipated provider errors into a fabricated friction log.

Optional friction entry template: attempted task; reproducible steps; expected/actual behavior; severity; workaround; suggested improvement; supporting evidence. Leave it out if you have no real observation to report.

## External actions the entrant must finish

- [ ] Rehearse [DEMO_SCRIPT.md](DEMO_SCRIPT.md) against the final code and record the actual flow. Check cancellation and refresh on screen.
- [ ] Upload the video and test its link from a signed-out browser. Replace the placeholder above.
- [ ] Review code/assets for secrets and ownership, choose an appropriate license or private sharing arrangement, publish/share the GitHub repository, and verify its accessibility. No repository publication is performed by this draft.
- [ ] Test README setup from a fresh checkout; record your tested platform and any remaining limitations.
- [ ] Fill all bracketed fields, revise feedback to your own experience, and ensure the description matches the recorded provider mode.
- [ ] Sign in to Devpost, join the event, create/edit the project, select Alexa+, and enter the links and final English description. Do not select unsupported mini-challenges.
- [ ] Personally verify eligibility and required repository sharing against the linked official rules.
- [ ] Submit the project using Devpost's final submission action, verify its submitted status, and retain confirmation. This document and a saved draft do not complete entry.

## Evidence boundary

Final hardening has 219 passing backend tests and 3 skipped opt-in live tests. Contract, build and simulated-voice/personal-day browser checks passed. The separate authorized live Gemini task-draft test timed out at both tested budgets, so successful live task creation is not claimed. Exact output is recorded in [RELEASE_PROGRESS.md](RELEASE_PROGRESS.md). Voice input and speech synthesis are implemented using the browser Web Speech API; Gemini can propose task changes and schedules, with explicit human approval required for persistence. The code has been published to GitHub; public hosting, video upload and Devpost submission remain external entrant actions.
