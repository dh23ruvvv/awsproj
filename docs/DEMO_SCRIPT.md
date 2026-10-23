# FlowPilot personal-planner demo

Use the README run commands. Start the built app at http://127.0.0.1:8000 and keep the offline planner selected. This walkthrough uses actual user input, without seeded sample tasks.

1. Select a date with the Planning day picker. Show its computed weekday and empty task list.
2. Choose Plan my day. Add Prepare presentation (60 minutes) and Read a chapter (30 minutes). Show that these are tasks, not calendar entries.
3. Choose Preview my day. Inspect the proposed timeline; cancel once to demonstrate that nothing was scheduled. Preview again and confirm.
4. Choose Add an interruption. Enter Call with Alex, 09:30-10:00. Preview the event and moved work, then confirm. Show the exact event name and the protected calendar block.
5. Choose Fixed plan / routine. Name it Weekend learning, select Tue, Sat and Sun, and add Study (30 minutes). Save. Open the next matching day and show the task. Refresh and verify it occurs once. Open a nonmatching day and show that it is empty.
6. Return to the first day to demonstrate independent saved schedules. End on the approval requirement and Alexa+ simulation label.

Target a recording shorter than three minutes. Rehearse before recording; this file is not evidence of a recorded video. Preferred hours are 09:00-17:00, with overflow up to 21:00 when deadlines permit. Long tasks can split into gaps while preserving their full duration. Routine tasks populate on opening matching days. Calendar changes always require confirmation. Expand Tool Execution Trace to show read/propose calls, arguments, results and timings. An optional MCP demo can create a task draft and follow its review link into this same UI; see the Agent Skill and README for connection details.

Automated browser check: `python scripts/browser_personal_days.py --url http://127.0.0.1:8000`.
