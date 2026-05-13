#!/usr/bin/env bash
# PostToolUse hook for Write|Edit:
# - Reads the edited file path from stdin JSON
# - If it's a Python file, runs a quick syntax check
# - Output goes back to Claude as additional context

set -uo pipefail

payload=$(cat)
file_path=$(echo "$payload" | jq -r '.tool_response.filePath // .tool_input.file_path // empty')

# Skip non-Python files silently
case "$file_path" in
    *.py) ;;
    *) exit 0 ;;
esac

# Skip if file doesn't exist on disk yet
[ -f "$file_path" ] || exit 0

if python -m py_compile "$file_path" 2>/tmp/py_compile_err; then
    echo "[post-edit] syntax OK: $file_path"
else
    echo "[post-edit] SYNTAX ERROR in $file_path:"
    cat /tmp/py_compile_err
    exit 2  # exit code 2 = blocking error fed back to Claude
fi
