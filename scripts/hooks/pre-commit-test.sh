#!/usr/bin/env bash
# Pre-commit test hook: block git commit if tests fail.
# Receives JSON on stdin: {"tool_name":"Bash","tool_input":{"command":"...","description":"..."}}

set -euo pipefail

# Read full stdin into a temp file to avoid quoting issues
TMPFILE=$(mktemp)
cat > "$TMPFILE"

# Extract the bash command from the JSON payload using Python
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
