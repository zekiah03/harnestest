#!/usr/bin/env bash
# Stop hook: prints a one-line summary of test/lint status to the UI.

set -uo pipefail

# Discard stdin (we don't need it)
cat >/dev/null

summary="harnestest:"

if command -v pytest >/dev/null 2>&1 && [ -f test_todo.py ]; then
    if pytest -q --no-header test_todo.py >/tmp/pytest.out 2>&1; then
        passed=$(grep -oE '[0-9]+ passed' /tmp/pytest.out | head -1)
        summary="$summary tests=${passed:-pass}"
    else
        summary="$summary tests=FAIL"
    fi
else
    summary="$summary tests=skip"
fi

# Count untracked files
if git rev-parse --git-dir >/dev/null 2>&1; then
    untracked=$(git status --porcelain | grep -c '^??' || true)
    summary="$summary, untracked=$untracked"
fi

jq -nc --arg msg "$summary" '{ systemMessage: $msg }'
