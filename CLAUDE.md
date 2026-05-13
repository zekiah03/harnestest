# Harness Practice Project

A small Python TODO list used as a sandbox for practicing Claude Code harness
features (hooks, settings, skills, subagents, plugins).

## Project layout

- `todo.py` — in-memory TodoList with `add`, `complete`, `remove`, `pending`
- `test_todo.py` — pytest suite covering every public method
- `.claude/hooks/` — example SessionStart, PreToolUse, PostToolUse, Stop hooks
- `.claude/settings.json` — team-shared settings and hook registrations
- `.claude/settings.local.json` — personal settings (gitignored)

## Running and verifying

- Tests: `python -m pytest -v`
- Syntax check: `python -m py_compile <file>` (also wired into the PostToolUse hook)

Always run the full test suite before saying a change is complete. A green
SessionStart hook with `Test count: 5` is the baseline — if a test is removed,
update the hook output and the count above.

## Coding conventions

- Type-hint every public function (parameters and return).
- Prefer `@dataclass` over hand-written `__init__` for simple records.
- Raise `KeyError` / `ValueError` rather than returning sentinel values; tests
  assert with `pytest.raises`.
- No comments that restate what the code already says — keep them only for
  non-obvious WHY.

## Hooks reference (for self-understanding)

The hook scripts under `.claude/hooks/` are the canonical examples for this
sandbox. When adding a new hook:

1. Write the script under `.claude/hooks/`.
2. Pipe-test with synthetic stdin: `echo '{...}' | ./hook.sh`.
3. Register in `.claude/settings.json` under the right event + matcher.
4. Validate with `jq -e '.hooks.<Event>[].hooks[].command' .claude/settings.json`.

## Git workflow

- Branch: `claude/harness-testing-practice-qnCnr` (never push to a different
  branch without explicit permission).
- Create new commits — do not amend pushed commits.
- A Stop hook (`stop_summary.sh`) reports pytest result + untracked count at
  end of each response; untracked > 0 means something needs to be committed.
