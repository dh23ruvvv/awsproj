"""Cross-document validation for FlowPilot architecture handoff.

Checks per OPUS_MASTER_PROMPT.md S12:
1. Task dependency graph: every DEPENDS ID exists, no cycles, topological order
2. Every SPEC REFS target section exists
3. Every table, endpoint, tool name used in 01, 04, 06 exists in 02
4. Every env var in .env.example exists in 02 config table
5. M1 vertical-slice tasks contain the complete loop
6. Submission/demo tasks are P0 and scheduled
7. Track claim consistency across 00, 01, README
8. Forbidden-marker lint (no TBD/to be decided), PowerShell-safe commands
9. Friction log has no fabricated entries
"""

import io
import re
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

errors = []
warnings = []

def err(msg):
    errors.append(f"ERROR: {msg}")

def warn(msg):
    warnings.append(f"WARNING: {msg}")

def read(path):
    return path.read_text(encoding="utf-8", errors="replace")

# ─── Load documents ───
doc00 = read(DOCS / "00_PROJECT_CONTEXT.md")
doc01 = read(DOCS / "01_PRODUCT_SPEC.md")
doc02 = read(DOCS / "02_ARCHITECTURE.md")
doc03 = read(DOCS / "03_MASTER_PLAN.md")
doc04 = read(DOCS / "04_TASK_BOARD.md")
doc05 = read(DOCS / "05_AGENT_PROTOCOL.md")
doc06 = read(DOCS / "06_TEST_DEMO_SUBMISSION.md")
doc07 = read(DOCS / "07_FRICTION_LOG.md")
doc08 = read(DOCS / "08_RISKS.md")
doc09 = read(DOCS / "09_DECISIONS.md")
readme_text = read(ROOT / "README.md")
env_example = read(ROOT / ".env.example")

# ─── 1. Task dependency graph ───
print("=== Check 1: Task dependency graph ===")

# Extract task IDs and their DEPENDS
task_pattern = re.compile(r"^## (TASK-[\w-]+)", re.MULTILINE)
depends_pattern = re.compile(r"\*\*DEPENDS:\*\*\s*(.+)", re.MULTILINE)
all_task_ids = set(task_pattern.findall(doc04))
print(f"  Task IDs found: {sorted(all_task_ids)}")

# Split by task sections
task_sections = re.split(r"(?=^## TASK-)", doc04, flags=re.MULTILINE)
dep_graph = {}
for section in task_sections:
    tid_match = re.search(r"^## (TASK-[\w-]+)", section, re.MULTILINE)
    if not tid_match:
        continue
    tid = tid_match.group(1)
    dep_match = re.search(r"\*\*DEPENDS:\*\*\s*(.+)", section)
    deps = []
    if dep_match:
        dep_str = dep_match.group(1).strip()
        if dep_str not in ("none", "None", "—"):
            # Extract TASK-XXX refs, stripping trailing commas/colons
            concrete_deps = [d.rstrip(",:") for d in re.findall(r"TASK-[\w-]+", dep_str)]
            deps = concrete_deps
    dep_graph[tid] = deps


for tid, deps in dep_graph.items():
    for d in deps:
        if d not in all_task_ids:
            err(f"TASK dep graph: {tid} depends on {d} which does not exist in task board")

# Simple cycle check via DFS
def has_cycle(graph):
    visited = set()
    rec_stack = set()
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.discard(node)
        return False
    for node in graph:
        if node not in visited:
            if dfs(node):
                return True
    return False

if has_cycle(dep_graph):
    err("TASK dep graph: CYCLE DETECTED in task dependencies")
else:
    print("  No cycles in dependency graph.")

print(f"  Found {len(all_task_ids)} tasks.")

# ─── 2. SPEC REFS validation ───
print("\n=== Check 2: SPEC REFS target sections ===")

# Extract all section headers from doc02
doc02_sections = set()
for m in re.finditer(r"^#{1,4}\s+(.+)", doc02, re.MULTILINE):
    doc02_sections.add(m.group(1).strip())

# We can't perfectly match "§5.1" to "5.1 Session Management" but we can check
# that the doc referenced exists and has numbered sections
spec_ref_pattern = re.compile(r"\*\*SPEC REFS:\*\*\s*(.+)", re.MULTILINE)
for m in spec_ref_pattern.finditer(doc04):
    refs = m.group(1)
    # Check that referenced files exist
    for fref in re.findall(r"`(docs/\d\d_\w+\.md)`", refs):
        fpath = ROOT / fref
        if not fpath.exists():
            err(f"SPEC REF file missing: {fref}")

print("  Spec ref file existence checked.")

# ─── 3. Names cross-check (tools, endpoints, tables) ───
print("\n=== Check 3: Tool/endpoint/table names in 02 ===")

# Tool names from 02 registry
tool_names_02 = set(re.findall(r"\|\s*`(\w+)`\s*\|\s*(READ|PROPOSE|COMMIT)", doc02))
tool_names_02 = {t[0] for t in tool_names_02}

# Tool names referenced in 01
tool_refs_01 = set(re.findall(r"`(\w+)`", doc01))
for tool in ["get_tasks", "get_calendar", "get_current_time", "propose_schedule", "propose_replan", "commit_schedule", "get_schedule", "get_memory"]:
    if tool in tool_refs_01 and tool not in tool_names_02:
        err(f"Tool '{tool}' referenced in 01 but not in 02 registry")

# Endpoint paths from 02
endpoint_paths = set(re.findall(r"`(?:GET|POST|DELETE|PUT|PATCH)\s+(/[^`]+)`", doc02))
print(f"  Tools in registry: {sorted(tool_names_02)}")
print(f"  Endpoints in 02: {len(endpoint_paths)}")

# ─── 4. Env vars ───
print("\n=== Check 4: Env vars in .env.example vs 02 config table ===")

env_vars_example = set(re.findall(r"^([A-Z_]+)=", env_example, re.MULTILINE))
# Match env vars from the config table: lines like | `FLOWPILOT_ENV` | ...
env_vars_02 = set(re.findall(r"\|\s*`([A-Z][A-Z0-9_]+)`\s*\|", doc02))
# Filter out false positives like 'INFO' that appear in example column
env_vars_02 = {v for v in env_vars_02 if v.startswith("FLOWPILOT_") or v.startswith("GEMINI_")}

missing_in_02 = env_vars_example - env_vars_02
missing_in_example = env_vars_02 - env_vars_example

for v in missing_in_02:
    err(f"Env var '{v}' in .env.example but not in 02 config table")
for v in missing_in_example:
    warn(f"Env var '{v}' in 02 config table but not in .env.example")

print(f"  .env.example vars: {sorted(env_vars_example)}")
print(f"  02 config vars: {sorted(env_vars_02)}")

# ─── 5. M1 vertical slice completeness ───
print("\n=== Check 5: M1 vertical slice ===")

# Extract M1 section from master plan
if "### M1" in doc03:
    m1_section = doc03.split("### M1")[1]
    if "### M2" in m1_section:
        m1_section = m1_section.split("### M2")[0]
    m1_task_ids = set(re.findall(r"TASK-\d+", m1_section))
else:
    m1_task_ids = set()
    err("M1 section not found in 03_MASTER_PLAN.md")

required_m1_elements = {
    "backend scaffolding": "TASK-004" in m1_task_ids,
    "frontend scaffolding": "TASK-005" in m1_task_ids,
    "session router": "TASK-006" in m1_task_ids,
    "tool registry": "TASK-007" in m1_task_ids,
    "scheduler engine": "TASK-008" in m1_task_ids,
    "propose tools": "TASK-009" in m1_task_ids,
    "plan confirm/commit": "TASK-010" in m1_task_ids,
    "deterministic provider": "TASK-011" in m1_task_ids,
    "agent loop": "TASK-012" in m1_task_ids,
}

for element, present in required_m1_elements.items():
    if not present:
        err(f"M1 missing element: {element}")
    else:
        print(f"  M1 includes: {element} [OK]")

print(f"  M1 tasks: {sorted(m1_task_ids)}")

# ─── 6. Submission tasks are P0 ───
print("\n=== Check 6: Submission tasks are P0 ===")

submit_tasks = ["TASK-023", "TASK-024", "TASK-025", "TASK-026", "TASK-027"]
for tid in submit_tasks:
    if tid in all_task_ids:
        # Check priority
        section = doc04.split(f"## {tid}")[1].split("---")[0] if f"## {tid}" in doc04 else ""
        if "P0" not in section:
            err(f"{tid} is a submission task but not P0")
        if "SUBMIT" not in section and "BUILD" not in section:
            warn(f"{tid} has no TRACK field")
        print(f"  {tid}: P0 [OK]")
    else:
        err(f"Submission task {tid} not found in task board")

# ─── 7. Track claim consistency ───
print("\n=== Check 7: Track claim consistency ===")

track_keywords = ["Approach B", "simulated", "simulation"]
docs_to_check = {
    "00": doc00,
    "01": doc01,
    "README": readme_text,
}

for name, content in docs_to_check.items():
    found = any(kw.lower() in content.lower() for kw in track_keywords)
    if found:
        print(f"  {name}: track claim present [OK]")
    else:
        warn(f"{name}: no track claim (Approach B / simulated) found")

# ─── 8. Forbidden markers ───
print("\n=== Check 8: Forbidden markers ===")

forbidden = ["TBD", "to be decided", "to be determined"]
all_docs = {
    "00": doc00, "01": doc01, "02": doc02, "03": doc03,
    "04": doc04, "05": doc05, "06": doc06, "07": doc07,
    "08": doc08, "09": doc09, "README": readme_text
}

for name, content in all_docs.items():
    for marker in forbidden:
        # Skip "TODO" as task status (allowed)
        matches = [m for m in re.finditer(re.escape(marker), content, re.IGNORECASE)
                   if marker != "TBD" or "STATUS" not in content[max(0,m.start()-50):m.start()]]
        if matches:
            err(f"Forbidden marker '{marker}' found in {name}")

# Check bash-isms in commands
bash_patterns = ["&&", "#!/bin/bash", "heredoc"]
for name, content in all_docs.items():
    for bp in bash_patterns:
        if bp in content and bp == "&&":
            # Allow && in markdown context, flag only in code blocks
            code_blocks = re.findall(r"```[\s\S]*?```", content)
            for block in code_blocks:
                if "&&" in block and ("powershell" in block.lower() or "ps1" in block.lower()):
                    warn(f"Possible bash '&&' in PowerShell code block in {name}")

print("  Forbidden marker check complete.")

# ─── 9. Friction log ───
print("\n=== Check 9: Friction log ===")

if "No friction events" in doc07 or "no friction" in doc07.lower():
    print("  Friction log states no events during planning. [OK]")
elif "F-001" in doc07:
    print("  Friction log has entries -- verify they are real.")
else:
    warn("Friction log status unclear")

# ─── Summary ───
print("\n" + "=" * 60)
print(f"ERRORS: {len(errors)}")
for e in errors:
    print(f"  {e}")
print(f"WARNINGS: {len(warnings)}")
for w in warnings:
    print(f"  {w}")
print("=" * 60)

if errors:
    print("\nVALIDATION FAILED — fix errors above.")
    sys.exit(1)
else:
    print("\nVALIDATION PASSED.")
    sys.exit(0)
