# Sub-agent Dispatch Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a reusable Claude Code skill at `~/.claude/skills/subagent-dispatch/SKILL.md` that encodes the sub-agent dispatch pattern with permission pre-flight, preventing mid-flight permission denials when orchestrating parallel agents.

**Architecture:** A pure markdown skill file — no executable code — that Claude reads when `/subagent-dispatch` is invoked. It provides a battle-tested checklist: pre-flight probe, dispatch template with explicit tool grants, error recovery fallback to main-agent execution, and batch commit pattern. The skill is self-contained and project-agnostic.

**Tech Stack:** Claude Code skills (markdown), Claude Code sub-agent dispatch (Agent tool), Write tool, Bash tool

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `~/.claude/skills/subagent-dispatch/SKILL.md` | Create | Complete orchestration cheat sheet with pre-flight, dispatch, error recovery, and batch commit patterns |

---

## Task 1: Write the skill file

**Files:**
- Create: `~/.claude/skills/subagent-dispatch/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p /Users/alexandromartini/.claude/skills/subagent-dispatch
```

Expected: no output, exit 0.

- [ ] **Step 2: Write the SKILL.md file**

Write the following to `/Users/alexandromartini/.claude/skills/subagent-dispatch/SKILL.md`:

```markdown
---
name: subagent-dispatch
description: >
  Encodes the sub-agent dispatch pattern with permission pre-flight for Claude Code.
  Use when orchestrating 2+ parallel sub-agents that need Write or Bash access,
  to prevent mid-flight permission denials. Invoke with /subagent-dispatch.
---

# Sub-agent Dispatch with Permission Pre-flight

Use this cheat sheet whenever you are about to spawn sub-agents that will write
files or run shell commands. Follow all five phases in order.

---

## Phase 1 — Permission Pre-flight

Before dispatching any sub-agents, probe that Write and Bash are live in this session.

### 1a. Write probe

Run this in a Bash tool call:

```bash
python3 -c "
import pathlib, tempfile, sys
p = pathlib.Path(tempfile.mktemp(suffix='.probe'))
try:
    p.write_text('ok')
    p.unlink()
    print('WRITE_OK')
except Exception as e:
    print(f'WRITE_DENIED: {e}')
    sys.exit(1)
"
```

If output is `WRITE_OK` → proceed to Phase 2.
If output is `WRITE_DENIED` → skip directly to Phase 4.

### 1b. Bash probe

```bash
echo "BASH_OK"
```

If output is `BASH_OK` → proceed to Phase 2.
Any permission error → skip to Phase 4.

---

## Phase 2 — Dispatch Pattern

Spawn each sub-agent as an independent Agent tool call. All independent sub-agents
MUST be launched in a single message (parallel Agent tool calls). Wait for all to
return before proceeding to Phase 3.

### Dispatch template (use for each parallel task)

```
Agent task: "<TASK_DESCRIPTION>"

You are working on: <PROJECT_ROOT>
Output file: <ABSOLUTE_OUTPUT_PATH>

Tools you will use:
- Read: read existing source files
- Write: write the output file
- Bash: run tests or linters if needed

Constraints:
- Do NOT modify any file other than <ABSOLUTE_OUTPUT_PATH>
- If any tool call is denied, stop immediately and return:
  {"status": "permission_denied", "tool": "<TOOL_NAME>", "detail": "<ERROR>"}
- On success, return:
  {"status": "ok", "output_file": "<ABSOLUTE_OUTPUT_PATH>"}
```

---

## Phase 3 — Error Recovery

After all sub-agents return, inspect each result:

**If any agent returned `permission_denied`:**
1. Log which task failed and which tool was denied.
2. Do NOT retry with another sub-agent.
3. Execute that task directly from the main agent (Phase 4 pattern).
4. Continue with outputs from successful agents.

**If any agent returned a malformed response (no `status` key):**
1. Check whether the output file exists and is valid.
2. If valid, treat as success.
3. If missing or invalid, execute directly (Phase 4).

---

## Phase 4 — Direct Execution Fallback

Use when pre-flight fails OR when recovering a denied sub-agent task.

Execute inline in the main agent session:
1. Read all required source files with the Read tool.
2. Write output with the Write tool (one file at a time).
3. Run validation with Bash if needed.

The main agent session already has the permissions granted at session start —
direct execution is always safe.

---

## Phase 5 — Batch Commit Pattern

Once all outputs are collected and validated:

### 5a. Validate outputs (for JSON tasks)

```bash
python3 << 'EOF'
import json, sys, pathlib

OUTPUT_DIR = "<ABSOLUTE_OUTPUT_DIR>"
schema_required_keys = ["id", "title"]  # adjust per project

errors = []
for path in sorted(pathlib.Path(OUTPUT_DIR).glob("*.json")):
    try:
        data = json.loads(path.read_text())
        missing = [k for k in schema_required_keys if k not in data]
        if missing:
            errors.append(f"{path.name}: missing keys {missing}")
    except json.JSONDecodeError as e:
        errors.append(f"{path.name}: invalid JSON — {e}")

if errors:
    print("VALIDATION ERRORS:")
    for e in errors:
        print(" ", e)
    sys.exit(1)
else:
    count = len(list(pathlib.Path(OUTPUT_DIR).glob("*.json")))
    print(f"All {count} files valid.")
EOF
```

### 5b. Stage and commit in organized batches

```bash
# Batch 1: new entity files
git add <OUTPUT_DIR>/entities/
git commit -m "feat: add <N> new entity definitions from sub-agent batch"

# Batch 2: updated index
git add <OUTPUT_DIR>/index.json
git commit -m "feat: update knowledge base index"
```

Replace `<OUTPUT_DIR>` and messages with project-specific values.
Never use `git add -A` or `git add .` — stage files by explicit path.

---

## Quick-reference Checklist

```
[ ] Phase 1a: Write probe passes (or fallback to Phase 4 confirmed)
[ ] Phase 1b: Bash probe passes (or fallback to Phase 4 confirmed)
[ ] Phase 2:  All sub-agents dispatched in parallel in one message
[ ] Phase 2:  Each agent has explicit output contract and tool list
[ ] Phase 3:  All agent results inspected for permission_denied / malformed
[ ] Phase 3:  Failed tasks retried directly from main agent (Phase 4)
[ ] Phase 4:  Direct execution used when pre-flight failed
[ ] Phase 5a: All output files validated
[ ] Phase 5b: Changes committed in organized batches (not git add -A)
```

---

## Common Pitfalls

| Pitfall | Prevention |
|---------|-----------|
| Agent denied Write mid-flight, silently produces no output | Check `{"status": "permission_denied"}` in return value |
| Sub-agent modifies wrong files | Constrain with explicit output path in task description |
| Batch commit mixes unrelated changes | One `git add <path>` per logical category |
| JSON schema drift between agents | Define `schema_required_keys` once, validate all outputs together |
| Pre-flight passes but session permissions revoked mid-run | Phase 4 fallback may still be needed — design recovery to be cheap |
| Dispatching agents sequentially instead of in parallel | All independent agents in ONE message — separate messages = serial |
```

- [ ] **Step 3: Verify the skill file exists and contains required sections**

```bash
python3 -c "
import pathlib
p = pathlib.Path('/Users/alexandromartini/.claude/skills/subagent-dispatch/SKILL.md')
assert p.exists(), 'File not found'
content = p.read_text()
for section in ['Pre-flight', 'Dispatch Pattern', 'Error Recovery', 'Direct Execution', 'Batch Commit']:
    assert section in content, f'Missing section: {section}'
print(f'OK — {len(content)} chars, {len(content.splitlines())} lines, all sections present')
"
```

Expected: `OK — <N> chars, <M> lines, all sections present`

- [ ] **Step 4: Confirm skill appears in skill directory**

```bash
ls /Users/alexandromartini/.claude/skills/
```

Expected output includes `subagent-dispatch`.

---

## Self-Review Checklist

- [x] Pre-flight covers both Write and Bash probes — Phase 1
- [x] Write probe uses tempfile (no side effects) — Phase 1a
- [x] Dispatch template includes explicit tool grants and output contract — Phase 2
- [x] Parallel dispatch emphasized (single message) — Phase 2
- [x] permission_denied and malformed response both handled — Phase 3
- [x] Direct execution fallback covers both pre-flight failure and recovery — Phase 4
- [x] JSON validation script with configurable required keys — Phase 5a
- [x] Batch commit uses explicit paths, not `git add -A` — Phase 5b
- [x] Quick-reference checklist covers all five phases — end of skill
- [x] Common pitfalls table includes "sequential dispatch" anti-pattern
