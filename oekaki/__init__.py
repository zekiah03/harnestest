"""お絵かきロジック (oekaki / nonograms / picross).

A daily logic puzzle: each row and column has a clue listing the run lengths
of filled cells (e.g. ``[3, 2, 1]`` means a run of 3, then 2, then 1, in that
order, separated by at least one empty cell). The player infers the unique
filled/empty state of every cell from the clues alone.

This package contains a constraint-propagation solver with backtracking, a
uniqueness checker (needed because a puzzle without a unique solution is
ambiguous and unfair), a curated set of bundled puzzles, deterministic
daily selection, and a tiny CLI for text-mode play.
"""

from oekaki.models import (
    Cell,
    Clue,
    Grid,
    Puzzle,
    bitmap_to_clues,
)
from oekaki.solver import (
    SolveError,
    enumerate_line_placements,
    has_unique_solution,
    propagate,
    solve,
)

__all__ = [
    "Cell",
    "Clue",
    "Grid",
    "Puzzle",
    "SolveError",
    "bitmap_to_clues",
    "enumerate_line_placements",
    "has_unique_solution",
    "propagate",
    "solve",
]

__version__ = "0.1.0"
