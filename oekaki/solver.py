"""Nonogram solver.

The strategy is the standard two-phase one:

1. **Constraint propagation.** For each line (row or column) we enumerate
   *every* placement of its clue that is consistent with the cells we
   already know. The intersection across all valid placements forces
   certain cells: a cell is *definitely filled* iff it is filled in every
   placement, *definitely empty* iff it is empty in every placement.
   Repeating row-then-column until no further progress is made is enough
   to solve most well-formed puzzles outright.

2. **Backtracking.** If propagation stalls with cells still unknown we
   pick an unknown cell, guess one of its two values, propagate again,
   and recurse. On failure we backtrack and try the other value. This
   guarantees correctness even on hard puzzles that resist pure logic.

Uniqueness — needed when generating or curating puzzles — is checked by
running the solver in a counting mode that explores both branches at
each backtrack point until two distinct solutions have been found.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

from oekaki.models import Cell, Puzzle


UNKNOWN = Cell.UNKNOWN
EMPTY = Cell.EMPTY
FILLED = Cell.FILLED


class SolveError(Exception):
    """Raised when a puzzle has no valid solution."""


# ---------------------------------------------------------------- single-line
def enumerate_line_placements(
    length: int,
    clues: Sequence[int],
    known: Sequence[int],
) -> Iterator[List[int]]:
    """Yield every 0/1 list of ``length`` cells that:

    - has its filled runs equal to ``clues`` in order, and
    - is consistent with ``known`` (a length-``length`` sequence of
      Cell.UNKNOWN / EMPTY / FILLED values — unknown cells are free).

    The empty clue ``[]`` yields exactly the all-empty placement (if
    consistent). Yields nothing if no valid placement exists.
    """
    if any(c <= 0 for c in clues):
        raise ValueError(f"clue runs must be positive: {clues!r}")

    known_list = list(known)
    if len(known_list) != length:
        raise ValueError("known length does not match line length")
    clues = list(clues)

    def cell_ok(pos: int, want: int) -> bool:
        k = known_list[pos]
        if k == UNKNOWN:
            return True
        return k == want

    def recur(start: int, idx: int) -> Iterator[List[int]]:
        """Place clue[idx], clue[idx+1], ... starting at ``start``."""
        if idx == len(clues):
            # All runs placed. Remaining cells must be empty.
            if all(cell_ok(p, EMPTY) for p in range(start, length)):
                yield [EMPTY] * (length - start)
            return
        run = clues[idx]
        # Tail = cells we still need *after* this run plus its separator.
        # That tail must fit: it is sum(remaining_runs) cells of fill,
        # plus the (len(remaining) - 1) separators between them. The
        # separator immediately *after* this run is counted in ``sep``
        # below, NOT in the tail length.
        remaining = clues[idx + 1 :]
        tail_len = sum(remaining) + max(0, len(remaining) - 1)
        sep = 1 if remaining else 0
        latest_start = length - run - sep - tail_len

        for offset in range(start, latest_start + 1):
            # Cells in [start, offset) are the gap before this run — they
            # must be EMPTY-compatible.
            if not all(cell_ok(p, EMPTY) for p in range(start, offset)):
                # If a known-FILLED cell sits in the prefix we cannot
                # push the run further right; bail out entirely.
                if any(known_list[p] == FILLED for p in range(start, offset)):
                    return
                continue
            # Cells [offset, offset+run) must be FILLED-compatible.
            if not all(cell_ok(p, FILLED) for p in range(offset, offset + run)):
                continue
            # If a separator is needed, it must be EMPTY-compatible.
            if sep and not cell_ok(offset + run, EMPTY):
                continue
            # Build the prefix and recurse for the rest of the clue.
            prefix = (
                [EMPTY] * (offset - start)
                + [FILLED] * run
                + ([EMPTY] if sep else [])
            )
            for tail in recur(offset + run + sep, idx + 1):
                yield prefix + tail

    if not clues:
        if all(cell_ok(p, EMPTY) for p in range(length)):
            yield [EMPTY] * length
        return

    yield from recur(0, 0)


def intersect_line(
    length: int,
    clues: Sequence[int],
    known: Sequence[int],
) -> List[int]:
    """Return new known-state after intersecting all valid placements.

    Cells that are filled in every valid placement become FILLED;
    cells empty in every valid placement become EMPTY; others stay
    UNKNOWN. The returned list is a *new* list — input is not mutated.

    Raises ``SolveError`` if there is no valid placement (i.e. the
    current state is inconsistent with the clues).
    """
    all_filled = [True] * length
    all_empty = [True] * length
    found = False
    for placement in enumerate_line_placements(length, clues, known):
        found = True
        for i, v in enumerate(placement):
            if v == FILLED:
                all_empty[i] = False
            else:
                all_filled[i] = False
        # Early exit: if neither all_filled nor all_empty is True
        # anywhere where the cell is still UNKNOWN, no further
        # placements can refine things — but we still need to keep
        # going to verify at least one placement exists. Cheap to skip.
    if not found:
        raise SolveError(f"no placement for clues {list(clues)} on {list(known)}")
    new = list(known)
    for i in range(length):
        if new[i] != UNKNOWN:
            continue
        if all_filled[i]:
            new[i] = FILLED
        elif all_empty[i]:
            new[i] = EMPTY
    return new


# ---------------------------------------------------------------- propagation
def _row(grid: List[List[int]], r: int) -> List[int]:
    return list(grid[r])


def _col(grid: List[List[int]], c: int) -> List[int]:
    return [grid[r][c] for r in range(len(grid))]


def _apply_row(grid: List[List[int]], r: int, new_row: List[int]) -> List[int]:
    """Write new_row into grid[r], returning the list of column indices
    where the value changed (i.e. moved from UNKNOWN to EMPTY/FILLED).
    """
    changed: List[int] = []
    for c, v in enumerate(new_row):
        if grid[r][c] != v:
            grid[r][c] = v
            changed.append(c)
    return changed


def _apply_col(grid: List[List[int]], c: int, new_col: List[int]) -> List[int]:
    changed: List[int] = []
    for r, v in enumerate(new_col):
        if grid[r][c] != v:
            grid[r][c] = v
            changed.append(r)
    return changed


def propagate(
    grid: List[List[int]],
    row_clues: Sequence[Sequence[int]],
    col_clues: Sequence[Sequence[int]],
) -> None:
    """Run constraint propagation to fixed point. Mutates ``grid``.

    Uses a dirty-line worklist: when a row changes any cell, the
    affected columns are scheduled for re-checking; when a column
    changes any cell, the affected rows are scheduled.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    dirty_rows = set(range(rows))
    dirty_cols = set(range(cols))
    while dirty_rows or dirty_cols:
        # Process rows.
        while dirty_rows:
            r = dirty_rows.pop()
            new_row = intersect_line(cols, row_clues[r], _row(grid, r))
            changed_cols = _apply_row(grid, r, new_row)
            for c in changed_cols:
                dirty_cols.add(c)
        # Then columns.
        while dirty_cols:
            c = dirty_cols.pop()
            new_col = intersect_line(rows, col_clues[c], _col(grid, c))
            changed_rows = _apply_col(grid, c, new_col)
            for r in changed_rows:
                dirty_rows.add(r)


# ---------------------------------------------------------------- top-level solve
def _is_complete(grid: List[List[int]]) -> bool:
    return all(v != UNKNOWN for row in grid for v in row)


def _first_unknown(grid: List[List[int]]) -> Optional[Tuple[int, int]]:
    """Pick the first unknown cell in row-major order.

    A smarter heuristic — choose the cell whose row+column constraints
    leave the fewest placements — would be faster on adversarial inputs
    but adds complexity. Plain row-major order is more than adequate for
    20×20-class puzzles, which is our practical upper bound.
    """
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == UNKNOWN:
                return (r, c)
    return None


def solve(
    row_clues: Sequence[Sequence[int]],
    col_clues: Sequence[Sequence[int]],
    *,
    initial: Optional[List[List[int]]] = None,
) -> List[List[int]]:
    """Return a complete solution bitmap (1=filled, 0=empty).

    ``initial`` may be supplied to constrain the solver to grids
    consistent with a partial state (used by the hint engine). Cells
    in ``initial`` are interpreted directly (UNKNOWN/EMPTY/FILLED).

    Raises ``SolveError`` if there is no consistent solution.
    """
    rows = len(row_clues)
    cols = len(col_clues)
    if initial is None:
        grid = [[UNKNOWN] * cols for _ in range(rows)]
    else:
        if len(initial) != rows or any(len(r) != cols for r in initial):
            raise ValueError("initial grid shape does not match clues")
        grid = [list(r) for r in initial]

    try:
        propagate(grid, row_clues, col_clues)
    except SolveError:
        raise

    if _is_complete(grid):
        return [[1 if v == FILLED else 0 for v in row] for row in grid]

    pos = _first_unknown(grid)
    if pos is None:
        raise SolveError("propagation finished but grid not complete (bug?)")
    r, c = pos
    # Try FILLED before EMPTY — slightly biases toward earlier discovery
    # of dense patterns. Doesn't change correctness.
    for guess in (FILLED, EMPTY):
        branch = [list(row) for row in grid]
        branch[r][c] = guess
        try:
            return solve(row_clues, col_clues, initial=branch)
        except SolveError:
            continue
    raise SolveError(
        f"no solution found after branching on ({r}, {c})"
    )


# ---------------------------------------------------------------- uniqueness
def count_solutions(
    row_clues: Sequence[Sequence[int]],
    col_clues: Sequence[Sequence[int]],
    *,
    limit: int = 2,
) -> int:
    """Count distinct solutions, stopping early once ``limit`` are found.

    ``limit=2`` is the common case: we just want to know whether the
    puzzle has zero, one, or "many" solutions.
    """
    rows = len(row_clues)
    cols = len(col_clues)
    found: List[Tuple[Tuple[int, ...], ...]] = []

    def rec(grid: List[List[int]]) -> None:
        if len(found) >= limit:
            return
        try:
            propagate(grid, row_clues, col_clues)
        except SolveError:
            return
        if _is_complete(grid):
            snapshot = tuple(tuple(1 if v == FILLED else 0 for v in row) for row in grid)
            if snapshot not in found:
                found.append(snapshot)
            return
        pos = _first_unknown(grid)
        if pos is None:
            return
        r, c = pos
        for guess in (FILLED, EMPTY):
            branch = [list(row) for row in grid]
            branch[r][c] = guess
            rec(branch)
            if len(found) >= limit:
                return

    rec([[UNKNOWN] * cols for _ in range(rows)])
    return len(found)


def has_unique_solution(
    row_clues: Sequence[Sequence[int]],
    col_clues: Sequence[Sequence[int]],
) -> bool:
    """True iff the puzzle has exactly one solution."""
    return count_solutions(row_clues, col_clues, limit=2) == 1


# ---------------------------------------------------------------- hint
def next_deducible(
    puzzle: Puzzle,
    cells: List[List[int]],
) -> Optional[Tuple[int, int, int]]:
    """Given a player's current cells, return the next cell that *must*
    take a specific value (FILLED or EMPTY) by pure logic, or None if
    nothing is forced (in which case the player must guess).

    Returns ``(row, col, value)`` with ``value`` being EMPTY or FILLED.

    Implementation: run one round of constraint propagation from the
    player's current state — but treat any player-set value that
    *disagrees* with the unique solution as if the player hadn't set
    it. (Otherwise an inconsistent guess would crash the solver and we'd
    have nothing to suggest.)
    """
    rows = puzzle.rows
    cols = puzzle.cols
    # Build a propagation input where the player's mistakes are wiped.
    sol = puzzle.solution
    work: List[List[int]] = [[UNKNOWN] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            v = cells[r][c]
            if v == FILLED and sol[r][c] == 1:
                work[r][c] = FILLED
            elif v == EMPTY and sol[r][c] == 0:
                work[r][c] = EMPTY
            # All other cases (UNKNOWN, or player mistakes) → stay UNKNOWN
    try:
        propagate(work, puzzle.row_clues, puzzle.col_clues)
    except SolveError:
        return None
    # Find the first cell that propagation has now determined but the
    # player has not yet correctly set.
    for r in range(rows):
        for c in range(cols):
            v = work[r][c]
            if v == UNKNOWN:
                continue
            player = cells[r][c]
            if player == v:
                continue
            return (r, c, v)
    return None
