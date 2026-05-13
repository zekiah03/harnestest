#!/usr/bin/env bash
# PreToolUse hook for Bash: blocks obviously dangerous commands.
# Returns a JSON permission decision to deny the tool call before it runs.

set -uo pipefail

payload=$(cat)
cmd=$(echo "$payload" | jq -r '.tool_input.command // empty')

deny() {
    local reason="$1"
    jq -nc \
      --arg reason "$reason" \
      '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: $reason
        }
      }'
    exit 0
}

# Patterns to refuse
case "$cmd" in
    *"rm -rf /"*|*"rm -rf /*"*)
        deny "Refused: 'rm -rf /' family targets root filesystem."
        ;;
    *":(){ :|:& };:"*)
        deny "Refused: fork bomb pattern detected."
        ;;
    *"git push --force"*|*"git push -f "*)
        deny "Refused: force-push requires explicit human approval."
        ;;
    *"git reset --hard"*)
        deny "Refused: 'git reset --hard' discards uncommitted work."
        ;;
    *"chmod -R 777"*)
        deny "Refused: recursive 777 is insecure."
        ;;
esac

# Default: allow (no output, exit 0)
exit 0
