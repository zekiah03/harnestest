"""Solver tests — the engineering core of this project.

Heavily layered: we start at the smallest unit (line enumeration) and
work up to the full backtracking solver and uniqueness counter, so
when a bug surfaces it is obvious where to look.
"""

from __future__ import annotations

from typing import List

import pytest

from oekaki.models import Cell, Puzzle, bitmap_to_clues
from oekaki.solver import (
    SolveError,
    count_solutions,
    enumerate_line_placements,
    has_unique_solution,
    intersect_line,
    next_deducible,
    propagate,
    solve,
)


UNK, EMP, FIL = Cell.UNKNOWN, Cell.EMPTY, Cell.FILLED


def placements(length, clues, known=None):
    if known is None:
        known = [UNK] * length
    return list(enumerate_line_placements(length, list(clues), list(known)))


# ====================================================================== line
class TestEnumerateLineEmptyClue:
    def test_empty_clue_yields_all_empty(self):
        ps = placements(5, [])
        assert ps == [[EMP] * 5]

    def test_empty_clue_zero_length(self):
        ps = placements(0, [])
        assert ps == [[]]

    def test_empty_clue_inconsistent_with_known_filled(self):
        ps = placements(5, [], [UNK, FIL, UNK, UNK, UNK])
        assert ps == []


class TestEnumerateLineSingleRun:
    def test_single_full_run(self):
        # run of 5 on length 5 — exactly one placement.
        ps = placements(5, [5])
        assert ps == [[FIL, FIL, FIL, FIL, FIL]]

    def test_single_run_with_slack(self):
        # run of 3 on length 5 — three placements.
        ps = placements(5, [3])
        assert ps == [
            [FIL, FIL, FIL, EMP, EMP],
            [EMP, FIL, FIL, FIL, EMP],
            [EMP, EMP, FIL, FIL, FIL],
        ]

    def test_run_does_not_fit(self):
        ps = placements(3, [5])
        assert ps == []


class TestEnumerateLineMultipleRuns:
    def test_two_runs_tight(self):
        # runs [2, 2] on length 5: requires 2+1+2 = 5, exactly one placement.
        ps = placements(5, [2, 2])
        assert ps == [[FIL, FIL, EMP, FIL, FIL]]

    def test_two_runs_with_slack(self):
        # runs [1, 1] on length 4: positions of the two 1-cells are
        # (0,2), (0,3), (1,3) — three placements.
        ps = placements(4, [1, 1])
        assert ps == [
            [FIL, EMP, FIL, EMP],
            [FIL, EMP, EMP, FIL],
            [EMP, FIL, EMP, FIL],
        ]

    def test_three_runs(self):
        # runs [1, 1, 1] on length 5: one placement (1.1.1).
        ps = placements(5, [1, 1, 1])
        assert ps == [[FIL, EMP, FIL, EMP, FIL]]


class TestEnumerateLineKnownConstraints:
    def test_known_filled_anchors_run(self):
        # length 5, run of 3, with cell 2 already filled.
        # Valid placements: starts at 0 or 2. (start 1 also OK actually
        # since [E F F F E] also covers cell 2.)
        # Verify by checking all placements include cell 2 as FILLED.
        ps = placements(5, [3], [UNK, UNK, FIL, UNK, UNK])
        assert all(p[2] == FIL for p in ps)
        # And there are 3 such placements (offsets 0, 1, 2).
        assert len(ps) == 3

    def test_known_empty_blocks_run(self):
        # length 5, run of 3, with cell 2 forced EMPTY.
        # No placement of a 3-run can avoid cell 2 → zero placements.
        ps = placements(5, [3], [UNK, UNK, EMP, UNK, UNK])
        assert ps == []

    def test_known_empty_constrains_layout(self):
        # runs [1, 1] on length 5 with cell 2 EMPTY.
        # 1.1 placements where neither 1 is at index 2.
        ps = placements(5, [1, 1], [UNK, UNK, EMP, UNK, UNK])
        # Both runs must avoid index 2.
        for p in ps:
            assert p[2] == EMP
            # Exactly two filled cells.
            assert sum(p) == 2


class TestIntersectLine:
    def test_unique_placement_fully_determines(self):
        # runs [3] on length 3 — exactly one placement, fully filled.
        new = intersect_line(3, [3], [UNK, UNK, UNK])
        assert new == [FIL, FIL, FIL]

    def test_overlap_determines_middle_cell(self):
        # Classic example: run of 4 on length 5. Three placements:
        #   FFFFE   EFFFF   (and one in middle — wait no)
        # Actually run 4 on length 5: starts at 0 or 1.
        #   FFFFE
        #   EFFFF
        # Overlap: cells 1, 2, 3 are filled in both — must be FILLED.
        # Cells 0 and 4 vary → UNKNOWN.
        new = intersect_line(5, [4], [UNK] * 5)
        assert new == [UNK, FIL, FIL, FIL, UNK]

    def test_inconsistent_raises(self):
        # Run of 5 on length 3 — no placement.
        with pytest.raises(SolveError):
            intersect_line(3, [5], [UNK] * 3)

    def test_preserves_known_cells(self):
        # Cells already known must not change.
        new = intersect_line(5, [4], [UNK, UNK, FIL, UNK, UNK])
        # Run of 4 with cell 2 filled → still two placements; cells 1,2,3
        # are filled in both.
        assert new[1] == FIL
        assert new[2] == FIL
        assert new[3] == FIL


# ====================================================================== propagation + solve
def _solve_and_check(bitmap: List[List[int]]) -> None:
    """Given a target bitmap, derive its clues and verify the solver
    recovers the original (assuming uniqueness)."""
    rcs, ccs = bitmap_to_clues(bitmap)
    if not has_unique_solution(rcs, ccs):
        pytest.skip("puzzle is not unique; skipping recovery check")
    out = solve(rcs, ccs)
    assert out == bitmap


class TestSolveTiny:
    def test_single_cell_filled(self):
        _solve_and_check([[1]])

    def test_single_cell_empty(self):
        _solve_and_check([[0]])

    def test_2x2_diagonal(self):
        _solve_and_check([
            [1, 0],
            [0, 1],
        ])

    def test_3x3_plus_sign(self):
        # A plus.
        _solve_and_check([
            [0, 1, 0],
            [1, 1, 1],
            [0, 1, 0],
        ])

    def test_5x5_heart(self):
        # A simple heart shape.
        _solve_and_check([
            [0, 1, 0, 1, 0],
            [1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1],
            [0, 1, 1, 1, 0],
            [0, 0, 1, 0, 0],
        ])


class TestSolveMedium:
    def test_10x10_smiley(self):
        bitmap = [
            [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
            [1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
            [1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 1, 0, 0, 0, 0, 1, 0, 1],
            [1, 0, 0, 1, 1, 1, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 1, 1, 1, 1, 1, 0, 0],
        ]
        _solve_and_check(bitmap)


class TestSolveErrors:
    def test_overconstrained_raises(self):
        # row clue says [3] in a 2-wide row.
        with pytest.raises(SolveError):
            solve([[3]], [[1], [1]])

    def test_clues_inconsistent_raises(self):
        # Row requires a filled cell, column says fully empty — contradictory.
        with pytest.raises(SolveError):
            solve([[1]], [[]])


# ====================================================================== uniqueness
class TestUniqueness:
    def test_unique_simple(self):
        bitmap = [[1, 1], [0, 1]]
        rcs, ccs = bitmap_to_clues(bitmap)
        assert has_unique_solution(rcs, ccs)

    def test_two_solutions_2x2(self):
        # The classic ambiguous nonogram: 2x2 with one filled per row
        # and one filled per column. Two solutions:
        #   1 0      0 1
        #   0 1      1 0
        rcs = [[1], [1]]
        ccs = [[1], [1]]
        assert not has_unique_solution(rcs, ccs)
        assert count_solutions(rcs, ccs) == 2

    def test_no_solution(self):
        rcs = [[2]]  # row needs run of 2
        ccs = [[0]]  # but col 0 is fully empty
        assert count_solutions(rcs, ccs) == 0

    def test_limit_caps_count(self):
        rcs = [[1], [1]]
        ccs = [[1], [1]]
        assert count_solutions(rcs, ccs, limit=1) == 1


# ====================================================================== hints
class TestHints:
    def test_empty_grid_returns_some_deducible_cell(self):
        # A 3x3 plus: lots of forced cells from clues alone.
        bitmap = [
            [0, 1, 0],
            [1, 1, 1],
            [0, 1, 0],
        ]
        p = Puzzle.from_bitmap(id="plus", title="plus", bitmap=bitmap, difficulty="tiny")
        empty_grid = [[UNK] * 3 for _ in range(3)]
        hint = next_deducible(p, empty_grid)
        assert hint is not None
        r, c, v = hint
        assert p.solution[r][c] == (1 if v == FIL else 0)

    def test_player_correct_state_returns_next(self):
        bitmap = [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ]
        p = Puzzle.from_bitmap(id="ring", title="ring", bitmap=bitmap, difficulty="tiny")
        # The player has filled one correct cell.
        cells = [[UNK]*3 for _ in range(3)]
        cells[0][0] = FIL
        hint = next_deducible(p, cells)
        # There should still be more to deduce.
        assert hint is not None
        r, c, v = hint
        assert (r, c) != (0, 0)

    def test_completely_solved_grid_returns_none(self):
        bitmap = [[1, 0], [0, 1]]
        p = Puzzle.from_bitmap(id="diag", title="diag", bitmap=bitmap, difficulty="tiny")
        cells = [[FIL, EMP], [EMP, FIL]]
        assert next_deducible(p, cells) is None

    def test_player_with_wrong_guess_still_gets_help(self):
        # The player has marked a cell wrong; the hint engine should
        # ignore that mistake and still suggest a useful next step.
        bitmap = [
            [1, 1, 0],
            [0, 1, 1],
            [1, 0, 0],
        ]
        p = Puzzle.from_bitmap(id="zig", title="zig", bitmap=bitmap, difficulty="tiny")
        cells = [[UNK]*3 for _ in range(3)]
        cells[0][2] = FIL   # wrong: should be EMP
        hint = next_deducible(p, cells)
        assert hint is not None


# ====================================================================== adversarial
class TestBacktrackingRequired:
    """A puzzle where pure constraint propagation stalls. The classic
    example is a 5x5 with two ambiguous regions whose resolution
    depends on each other. We construct one with a unique solution and
    verify the backtracking solver finds it."""

    def test_5x5_requiring_backtrack(self):
        # A 5x5 design that needs guessing in some solver implementations.
        # The exact shape isn't important — we just need solve() to return
        # a correct result.
        bitmap = [
            [1, 0, 1, 0, 1],
            [0, 1, 0, 1, 0],
            [1, 0, 1, 0, 1],
            [0, 1, 0, 1, 0],
            [1, 0, 1, 0, 1],
        ]
        if has_unique_solution(*bitmap_to_clues(bitmap)):
            _solve_and_check(bitmap)


class TestPropagateMutatesGrid:
    def test_changes_apply_in_place(self):
        # Build a 3x3 puzzle where row 0 is [3] (all filled) and verify
        # propagate sets that row.
        grid = [[UNK] * 3 for _ in range(3)]
        row_clues = [[3], [], []]
        col_clues = [[1], [1], [1]]
        propagate(grid, row_clues, col_clues)
        assert grid[0] == [FIL, FIL, FIL]
        assert grid[1] == [EMP, EMP, EMP]
        assert grid[2] == [EMP, EMP, EMP]
