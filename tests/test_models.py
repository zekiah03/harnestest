"""Tests for the domain models."""

import pytest

from oekaki.models import Cell, Clue, Grid, Puzzle, bitmap_to_clues


class TestClue:
    def test_empty_clue_min_length_is_zero(self):
        assert Clue(()).min_length() == 0

    def test_single_run(self):
        assert Clue((3,)).min_length() == 3

    def test_runs_need_separators(self):
        # [2, 3, 1] needs 2 + 1 + 3 + 1 + 1 = 8 cells minimum.
        assert Clue((2, 3, 1)).min_length() == 8

    def test_parse_accepts_iterable(self):
        assert Clue.parse([1, 2]).runs == (1, 2)
        assert Clue.parse(Clue((4,))).runs == (4,)
        assert Clue.parse(None).runs == ()


class TestBitmapToClues:
    def test_empty_row_yields_empty_clue(self):
        rows, cols = bitmap_to_clues([[0, 0, 0]])
        assert rows == [[]]
        assert cols == [[], [], []]

    def test_full_row(self):
        rows, cols = bitmap_to_clues([[1, 1, 1]])
        assert rows == [[3]]
        assert cols == [[1], [1], [1]]

    def test_mixed(self):
        rows, cols = bitmap_to_clues([
            [1, 0, 1, 1],
            [1, 1, 0, 1],
        ])
        assert rows == [[1, 2], [2, 1]]
        assert cols == [[2], [1], [1], [2]]

    def test_non_rectangular_rejected(self):
        with pytest.raises(ValueError):
            bitmap_to_clues([[1, 1], [1]])


class TestPuzzleValidation:
    def _ok_bitmap(self):
        return [[1, 0], [0, 1]]

    def test_consistent_puzzle_builds(self):
        p = Puzzle.from_bitmap(id="x", title="X", bitmap=self._ok_bitmap(), difficulty="tiny")
        assert p.rows == 2

    def test_inconsistent_row_clues_rejected(self):
        with pytest.raises(ValueError):
            Puzzle(
                id="x", title="X", rows=2, cols=2,
                row_clues=[[2], []],   # wrong: real row 0 has run [1]
                col_clues=[[1], [1]],
                solution=self._ok_bitmap(),
                difficulty="tiny",
            )

    def test_unknown_difficulty_rejected(self):
        with pytest.raises(ValueError):
            Puzzle.from_bitmap(id="x", title="X", bitmap=self._ok_bitmap(), difficulty="mythical")

    def test_clues_too_big_rejected(self):
        # row clue exceeds line length.
        with pytest.raises(ValueError):
            Puzzle(
                id="x", title="X", rows=1, cols=2,
                row_clues=[[3]],
                col_clues=[[0], [0]],
                solution=[[0, 0]],
                difficulty="tiny",
            )


class TestPuzzleSerialization:
    def test_round_trip(self):
        p = Puzzle.from_bitmap(
            id="x", title="X",
            bitmap=[[1, 0], [0, 1]],
            difficulty="tiny",
        )
        d = p.to_dict(include_solution=True)
        p2 = Puzzle.from_dict(d)
        assert p2.solution == p.solution
        assert p2.row_clues == [list(c) for c in p.row_clues]

    def test_to_dict_omits_solution_by_default(self):
        p = Puzzle.from_bitmap(id="x", title="X",
                               bitmap=[[1, 0], [0, 1]], difficulty="tiny")
        d = p.to_dict()
        assert "solution" not in d


class TestGrid:
    def test_default_is_unknown_everywhere(self):
        g = Grid(rows=2, cols=3)
        assert all(v == Cell.UNKNOWN for row in g.cells for v in row)

    def test_set_and_get(self):
        g = Grid(rows=2, cols=2)
        g.set(0, 1, Cell.FILLED)
        assert g.get(0, 1) == Cell.FILLED

    def test_invalid_cell_value_rejected(self):
        g = Grid(rows=1, cols=1)
        with pytest.raises(ValueError):
            g.set(0, 0, 7)

    def test_is_complete_only_when_no_unknowns(self):
        g = Grid(rows=1, cols=2, cells=[[Cell.FILLED, Cell.EMPTY]])
        assert g.is_complete()
        g2 = Grid(rows=1, cols=2)
        assert not g2.is_complete()

    def test_filled_bitmap_treats_unknown_as_empty(self):
        g = Grid(rows=1, cols=3, cells=[[Cell.FILLED, Cell.UNKNOWN, Cell.EMPTY]])
        assert g.filled_bitmap() == [[1, 0, 0]]

    def test_matches_solution(self):
        g = Grid(rows=2, cols=2, cells=[[Cell.FILLED, Cell.EMPTY],
                                          [Cell.EMPTY, Cell.FILLED]])
        assert g.matches([[1, 0], [0, 1]])

    def test_roundtrip_serialization(self):
        g = Grid(rows=2, cols=2, cells=[[Cell.FILLED, Cell.UNKNOWN],
                                          [Cell.EMPTY, Cell.FILLED]])
        g2 = Grid.from_dict(g.to_dict())
        assert g2.cells == g.cells
