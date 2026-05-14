"""Verify every bundled puzzle is well-formed and uniquely solvable.

A nonogram without a unique solution is a broken puzzle: the player
has no way to derive the answer from logic alone. This test is the
guard against accidentally shipping an ambiguous one.
"""

import pytest

from oekaki.puzzles import PUZZLES, get_puzzle, list_puzzles
from oekaki.solver import has_unique_solution, solve


@pytest.mark.parametrize("puzzle", PUZZLES, ids=lambda p: p.id)
class TestBundledPuzzles:
    def test_is_uniquely_solvable(self, puzzle):
        assert has_unique_solution(puzzle.row_clues, puzzle.col_clues), (
            f"puzzle {puzzle.id!r} has multiple solutions — please tighten clues"
        )

    def test_solver_recovers_canonical_solution(self, puzzle):
        recovered = solve(puzzle.row_clues, puzzle.col_clues)
        assert recovered == puzzle.solution

    def test_difficulty_is_known(self, puzzle):
        assert puzzle.difficulty in ("tiny", "easy", "medium", "hard")


class TestLookup:
    def test_get_by_id(self):
        p = get_puzzle("heart")
        assert p is not None
        assert p.title == "ハート"

    def test_unknown_id_returns_none(self):
        assert get_puzzle("nope") is None

    def test_list_filters_by_difficulty(self):
        tinies = list_puzzles("tiny")
        assert all(p.difficulty == "tiny" for p in tinies)
        assert tinies, "expected at least one tiny puzzle"


class TestCatalogShape:
    def test_ids_unique(self):
        ids = [p.id for p in PUZZLES]
        assert len(set(ids)) == len(ids)

    def test_titles_in_japanese(self):
        # Every title contains at least one CJK character.
        for p in PUZZLES:
            assert any(0x3040 <= ord(c) <= 0x9fff for c in p.title), p.id

    def test_no_emoji_in_titles(self):
        for p in PUZZLES:
            assert all(ord(c) < 0x1F000 for c in p.title), p.id
