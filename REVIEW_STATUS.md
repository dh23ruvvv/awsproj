# Review status

FlowPilot includes the Simulated Alexa+ Multimodal Web Experience and a working
Self-Hosted Streamable HTTP MCP Server at `/mcp` and `/api/v1/mcp`, protocol
`2025-11-25`. The [Agent Skill](skills/flowpilot-scheduler/SKILL.md) documents the
bindings and human review workflow. Amazon onboarding and certification remain
separate deployment steps.

Implemented and verified: live ToolTrace inspection, complete whole-day proposals,
partial task updates with explicit deadline clearing, long-task gap splitting,
controlled overflow to 21:00, named interruptions, and explicit preference memory
with UI deletion. Neither Gemini nor MCP can execute COMMIT tools. Task/calendar
changes require human confirmation; the separate preference tier writes only
memory and updates the state version.

Final gate: **263 passed, 3 skipped** in the backend suite; production build and
API contract passed; smoke **2 passed, 1 skipped**. The skipped tests are opt-in
live checks. All three were separately exercised successfully using
`gemini-3.5-flash-lite` with a 30-second budget.

Personal-day, simulated-voice and MCP review/preference browser checks passed at
320–1440px. Physical microphone capture and the browser's remote recognition
service were not tested. See [release evidence](docs/RELEASE_PROGRESS.md) for exact
results and [README](README.md) for setup.
