# Pre-commit Test Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PreToolUse hook to `~/.claude/settings.json` that runs the project's test suite before any `git commit`, blocking the commit if tests fail.

**Architecture:** A bash hook script at `~/.claude/hooks/pre-commit-test.sh` receives the Claude tool-call JSON on stdin, short-circuits on non-commit commands, auto-detects the test framework (pytest vs npm test), and exits non-zero to block on failure. The hook is registered in `~/.claude/settings.json` under the `hooks.PreToolUse` array. Settings patching is done with Python's `json` module to avoid clobbering the existing file.

**Tech Stack:** Bash 5, Python 3 (`json` stdlib), Claude Code hooks (PreToolUse), pytest, npm

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `~/.claude/hooks/pre-commit-test.sh` | Create | Parse stdin, detect project + test framework, run tests, exit 0/1 |
| `~/.claude/settings.json` | Modify | Add `hooks.PreToolUse` entry pointing at the script |

---

## Task 1: Write the hook script

**Files:**
- Create: `~/.claude/hooks/pre-commit-test.sh`

- [ ] **Step 1: Create the hooks directory**

```bash
mkdir -p /Users/alexandromartini/.claude/hooks
```

Expected: no output, exit 0.

- [ ] **Step 2: Write the hook script**

Write the following to `/Users/alexandromartini/.claude/hooks/pre-commit-test.sh`:

```bash
#!/usr/bin/env bash
# ~/.claude/hooks/pre-commit-test.sh
# PreToolUse hook: block git commit if tests fail.
# Receives JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"...","description":"..."}}

set -euo pipefail

# Read full stdin into a temp file to avoid quoting issues
TMPFILE=$(mktemp)
cat > "$TMPFILE"

# Extract the bash command from the JSON payload using Python (always available)
CMD=$(python3 -c "
import sys, json
with open(sys.argv[1]) as f:
    data = json.load(f)
print(data.get('tool_input', {}).get('command', ''))
" "$TMPFILE" 2>/dev/null || echo "")

rm -f "$TMPFILE"

# If we couldn't parse or command doesn't contain 'git commit', allow immediately
if [[ -z "$CMD" ]]; then
  exit 0
fi

if ! echo "$CMD" | grep -qE 'git\s+commit'; then
  exit 0
fi

# Detect the git repo root from current working directory
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")

if [[ -z "$PROJECT_ROOT" ]]; then
  # Not in a git repo — allow
  exit 0
fi

# Detect test framework
TEST_CMD=""

if [[ -f "$PROJECT_ROOT/pytest.ini" ]] || \
   [[ -f "$PROJECT_ROOT/pyproject.toml" ]] || \
   [[ -f "$PROJECT_ROOT/conftest.py" ]]; then
  TEST_CMD="python -m pytest -q"
elif [[ -f "$PROJECT_ROOT/package.json" ]]; then
  HAS_TEST=$(python3 -c "
import json, sys
with open('$PROJECT_ROOT/package.json') as f:
    pkg = json.load(f)
scripts = pkg.get('scripts', {})
print('yes' if 'test' in scripts else 'no')
" 2>/dev/null || echo "no")
  if [[ "$HAS_TEST" == "yes" ]]; then
    TEST_CMD="npm test"
  fi
fi

if [[ -z "$TEST_CMD" ]]; then
  # No recognized test framework — allow
  exit 0
fi

echo "==> [pre-commit-test] Running: $TEST_CMD (in $PROJECT_ROOT)" >&2

cd "$PROJECT_ROOT"
if $TEST_CMD; then
  echo "==> [pre-commit-test] Tests passed. Allowing commit." >&2
  exit 0
else
  echo "" >&2
  echo "==> [pre-commit-test] BLOCKED: Tests failed. Fix failing tests before committing." >&2
  exit 1
fi
```

Then make it executable:

```bash
chmod +x /Users/alexandromartini/.claude/hooks/pre-commit-test.sh
```

- [ ] **Step 3: Verify script is syntactically valid**

```bash
bash -n /Users/alexandromartini/.claude/hooks/pre-commit-test.sh && echo "Syntax OK"
```

Expected output: `Syntax OK`

---

## Task 2: Add hooks config to settings.json using Python

**Files:**
- Modify: `~/.claude/settings.json`

- [ ] **Step 4: Patch settings.json with Python (safe JSON merge)**

```bash
python3 << 'PYEOF'
import json

SETTINGS_PATH = "/Users/alexandromartini/.claude/settings.json"
HOOK_CMD = "/Users/alexandromartini/.claude/hooks/pre-commit-test.sh"

with open(SETTINGS_PATH, "r") as f:
    settings = json.load(f)

new_hook_entry = {
    "matcher": "Bash",
    "hooks": [
        {
            "type": "command",
            "command": HOOK_CMD
        }
    ]
}

# Ensure hooks key exists
if "hooks" not in settings:
    settings["hooks"] = {}

# Ensure PreToolUse list exists
if "PreToolUse" not in settings["hooks"]:
    settings["hooks"]["PreToolUse"] = []

# Avoid duplicates: remove any existing entry pointing to same command
settings["hooks"]["PreToolUse"] = [
    h for h in settings["hooks"]["PreToolUse"]
    if not any(
        hh.get("command") == HOOK_CMD
        for hh in h.get("hooks", [])
    )
]

# Append the new entry
settings["hooks"]["PreToolUse"].append(new_hook_entry)

with open(SETTINGS_PATH, "w") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("Done. hooks.PreToolUse now contains:")
for entry in settings["hooks"]["PreToolUse"]:
    print(" ", entry)
PYEOF
```

Expected output:
```
Done. hooks.PreToolUse now contains:
  {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': '/Users/alexandromartini/.claude/hooks/pre-commit-test.sh'}]}
```

- [ ] **Step 5: Verify the JSON is still valid after patching**

```bash
python3 -c "import json; json.load(open('/Users/alexandromartini/.claude/settings.json')); print('JSON valid')"
```

Expected: `JSON valid`

---

## Task 3: Verify end-to-end — pass case and fail case

- [ ] **Step 6: Confirm existing tests pass (baseline)**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
python -m pytest -q
```

Expected: all tests pass, exit 0.

- [ ] **Step 7: Simulate fail case — corrupt a test and verify commit is blocked**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
FIRST_TEST=$(python -m pytest --collect-only -q 2>/dev/null | grep '::' | head -1 | sed 's/::.*//')
echo "Temporarily corrupting: $FIRST_TEST"

python3 -c "
import sys
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()
with open(path, 'w') as f:
    f.write('THIS_IS_A_SYNTAX_ERROR\n' + content)
print('Corrupted', path)
" "$FIRST_TEST"

git add "$FIRST_TEST"
# The hook should block this commit
git commit -m "chore: this commit should be blocked by the hook"
echo "EXIT CODE: $?"
```

Expected: hook prints `==> [pre-commit-test] BLOCKED: Tests failed.` and the commit does not happen (exit code 1).

- [ ] **Step 8: Restore the corrupted file**

```bash
cd /Users/alexandromartini/Documents/dev/lagl-get
git checkout -- .
python -m pytest -q
```

Expected: all tests pass again.

---

## Self-Review Checklist

- [x] Non-commit Bash commands short-circuit immediately (no test overhead)
- [x] Hook auto-detects pytest (`pytest.ini`, `pyproject.toml`, `conftest.py`)
- [x] Hook auto-detects npm test (`package.json` with `test` script)
- [x] No recognized framework → allow (graceful no-op)
- [x] Settings patched with Python — existing keys preserved
- [x] Duplicate entries prevented on re-run
- [x] Fail case verified (Step 7)
- [x] Restore step included (Step 8)
