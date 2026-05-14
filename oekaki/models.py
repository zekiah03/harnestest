"""Domain types for お絵かきロジック.

The puzzle is a 2D grid. Each row and column carries a *clue* — an ordered
list of run lengths describing the filled runs in that line, separated by at
least one empty cell. For example a row clue of ``[3, 2]`` on a length-7
line admits the placements ``XXX.XX..`` (offset 0), ``XXX..XX.``, ``XXX..
.XX``, ``.XXX.XX.``, ``.XXX..XX``, ``..XXX.XX`` — six possibilities. The
solver narrows these down by intersecting valid placements row-by-row and
column-by-column until only one assignment remains.

Cell states for the *player's* working grid use three values:

  UNKNOWN (-1)  — the player has not yet touched this cell
  EMPTY    (0)  — the player has marked this cell as definitely empty
  FILLED   (1)  — the player has filled this cell in

Note that the player's EMPTY differs subtly from the solver's
"this cell is not part of any clue's run". They have the same logical
meaning ("not filled") but in the player's grid EMPTY is an explicit mark
the player made; cells the player hasn't touched are UNKNOWN.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple


# ---- cell sentinels ---------------------------------------------------
class Cell:
    """A namespace, not an enum — we store these as plain ints in lists."""
    UNKNOWN = -1
    EMPTY   = 0
    FILLED  = 1


@dataclass(frozen=True)
class Clue:
    """A clue for a single line. The empty clue ``()`` means the entire
    line is empty (no filled cells)."""

    runs: Tuple[int, ...] = ()

    def min_length(self) -> int:
        """Smallest line length that can hold this clue.

        Sum of all runs plus a forced gap of length 1 between consecutive
        runs (no gap before the first or after the last).
        """
        if not self.runs:
            return 0
        return sum(self.runs) + (len(self.runs) - 1)

    def to_list(self) -> List[int]:
        return list(self.runs)

    @classmethod
    def parse(cls, value: Any) -> "Clue":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls(())
        return cls(tuple(int(x) for x in value))


# ---- bitmap helpers ---------------------------------------------------
def bitmap_to_clues(bitmap: List[List[int]]) -> Tuple[List[List[int]], List[List[int]]]:
    """Derive row + column clues from a solution bitmap.

    ``bitmap[r][c] == 1`` means filled, anything else is treated as empty.
    Returns ``(row_clues, col_clues)``, each a list of lists of run lengths.
    """
    if not bitmap:
        return [], []
    rows = len(bitmap)
    cols = len(bitmap[0])
    if any(len(row) != cols for row in bitmap):
        raise ValueError("bitmap is not rectangular")

    def runs_of(line: List[int]) -> List[int]:
        out: List[int] = []
        current = 0
        for v in line:
            if v == 1:
                current += 1
            else:
                if current:
                    out.append(current)
                current = 0
        if current:
            out.append(current)
        return out

    row_clues = [runs_of(bitmap[r]) for r in range(rows)]
    col_clues = [runs_of([bitmap[r][c] for r in range(rows)]) for c in range(cols)]
    return row_clues, col_clues


# ---- Puzzle -----------------------------------------------------------
DIFFICULTIES = ("tiny", "easy", "medium", "hard")


@dataclass
class Puzzle:
    id: str
    title: str
    rows: int
    cols: int
    row_clues: List[List[int]]
    col_clues: List[List[int]]
    solution: List[List[int]]
    difficulty: str = "easy"

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("puzzle must have positive dimensions")
        if len(self.row_clues) != self.rows:
            raise ValueError(
                f"row_clues length {len(self.row_clues)} does not match rows {self.rows}"
            )
        if len(self.col_clues) != self.cols:
            raise ValueError(
                f"col_clues length {len(self.col_clues)} does not match cols {self.cols}"
            )
        if len(self.solution) != self.rows:
            raise ValueError("solution rows mismatch")
        if any(len(row) != self.cols for row in self.solution):
            raise ValueError("solution is not rectangular")
        if any(v not in (0, 1) for row in self.solution for v in row):
            raise ValueError("solution cells must be 0 or 1")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"unknown difficulty: {self.difficulty!r}")
        # Internal consistency: clues must match the solution.
        derived_row, derived_col = bitmap_to_clues(self.solution)
        if derived_row != [list(c) for c in self.row_clues]:
            raise ValueError("row_clues inconsistent with solution")
        if derived_col != [list(c) for c in self.col_clues]:
            raise ValueError("col_clues inconsistent with solution")
        # Clues must fit their lines.
        for r, clue in enumerate(self.row_clues):
            if Clue(tuple(clue)).min_length() > self.cols:
                raise ValueError(f"row {r} clue {clue} exceeds {self.cols} cols")
        for c, clue in enumerate(self.col_clues):
            if Clue(tuple(clue)).min_length() > self.rows:
                raise ValueError(f"col {c} clue {clue} exceeds {self.rows} rows")

    def total_filled(self) -> int:
        return sum(sum(row) for row in self.solution)

    def to_dict(self, include_solution: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "rows": self.rows,
            "cols": self.cols,
            "row_clues": [list(c) for c in self.row_clues],
            "col_clues": [list(c) for c in self.col_clues],
            "difficulty": self.difficulty,
        }
        if include_solution:
            data["solution"] = [list(r) for r in self.solution]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Puzzle":
        return cls(
            id=data["id"],
            title=data["title"],
            rows=int(data["rows"]),
            cols=int(data["cols"]),
            row_clues=[list(c) for c in data["row_clues"]],
            col_clues=[list(c) for c in data["col_clues"]],
            solution=[list(r) for r in data["solution"]],
            difficulty=data.get("difficulty", "easy"),
        )

    @classmethod
    def from_bitmap(
        cls,
        *,
        id: str,
        title: str,
        bitmap: List[List[int]],
        difficulty: str = "easy",
    ) -> "Puzzle":
        """Build a Puzzle from a solution bitmap, deriving clues automatically."""
        row_clues, col_clues = bitmap_to_clues(bitmap)
        return cls(
            id=id,
            title=title,
            rows=len(bitmap),
            cols=len(bitmap[0]) if bitmap else 0,
            row_clues=row_clues,
            col_clues=col_clues,
            solution=[list(r) for r in bitmap],
            difficulty=difficulty,
        )


# ---- Grid -------------------------------------------------------------
@dataclass
class Grid:
    """The player's working state — a 2D array of Cell values."""

    rows: int
    cols: int
    cells: List[List[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.cells:
            self.cells = [[Cell.UNKNOWN] * self.cols for _ in range(self.rows)]
        if len(self.cells) != self.rows or any(len(r) != self.cols for r in self.cells):
            raise ValueError("Grid cells shape mismatch")

    def set(self, r: int, c: int, value: int) -> None:
        if value not in (Cell.UNKNOWN, Cell.EMPTY, Cell.FILLED):
            raise ValueError(f"invalid cell value {value!r}")
        self.cells[r][c] = value

    def get(self, r: int, c: int) -> int:
        return self.cells[r][c]

    def is_complete(self) -> bool:
        """True if no cell is UNKNOWN."""
        return all(v != Cell.UNKNOWN for row in self.cells for v in row)

    def filled_bitmap(self) -> List[List[int]]:
        """Project the grid to a 0/1 bitmap (UNKNOWN treated as EMPTY)."""
        return [
            [1 if v == Cell.FILLED else 0 for v in row]
            for row in self.cells
        ]

    def matches(self, solution: List[List[int]]) -> bool:
        if len(solution) != self.rows:
            return False
        return self.filled_bitmap() == solution

    def to_dict(self) -> Dict[str, Any]:
        return {"rows": self.rows, "cols": self.cols, "cells": [list(r) for r in self.cells]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Grid":
        return cls(
            rows=int(data["rows"]),
            cols=int(data["cols"]),
            cells=[list(r) for r in data["cells"]],
        )

    @classmethod
    def from_cells(cls, cells: List[List[int]]) -> "Grid":
        return cls(rows=len(cells), cols=len(cells[0]) if cells else 0, cells=[list(r) for r in cells])
