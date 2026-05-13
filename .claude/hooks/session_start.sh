#!/usr/bin/env bash
# SessionStart hook: prints project status into the session context.
# Whatever this script writes to stdout becomes context Claude can read.

set -euo pipefail

echo "=== Harness Practice Project ==="
echo "Branch: $(git symbolic-ref --short HEAD 2>/dev/null || echo 'not a repo')"
echo "Python: $(python --version 2>&1)"

if command -v pytest >/dev/null 2>&1; then
    echo "pytest: $(pytest --version 2>&1 | head -1)"
else
    echo "pytest: NOT INSTALLED (run: pip install pytest)"
fi

# Show task count if todo files exist
test_count=$(grep -c "^def test_" test_todo.py 2>/dev/null || echo 0)
echo "Test count: ${test_count}"
echo "================================"
