# FlowPilot — Friction Log

> Log real friction events as they occur. Never fabricate entries.

## Schema

| Field | Description |
|---|---|
| ID | Sequential (F-001, F-002, …) |
| Timestamp | ISO8601 when friction occurred |
| Component | Amazon / MCP / Agentic tooling / SDK / Other |
| Task | Task ID being worked on |
| Steps | What was attempted |
| Expected | What should have happened |
| Actual | What actually happened |
| Severity | LOW / MEDIUM / HIGH |
| Workaround | How it was resolved |
| Recommendation | What would fix it permanently |

## Entries

No friction events were encountered during the architecture planning session. Entries will be added by Gemini and the Human during implementation as real friction is observed.
