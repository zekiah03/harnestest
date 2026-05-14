"""Curated puzzle catalogue.

Each puzzle is laid out as a multi-line string for readability — ``#``
marks a filled cell, anything else (typically ``.``) is empty. We parse
those into bitmaps at module load and let ``Puzzle.from_bitmap`` derive
the clues. A self-check at the bottom of the module verifies every
puzzle has a unique solution (run only via ``run_uniqueness_check`` so
import stays fast; the test suite calls it).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from oekaki.models import Puzzle


def _parse(art: str) -> List[List[int]]:
    """Turn a multi-line art string into a 0/1 bitmap."""
    lines = [line for line in art.strip("\n").splitlines() if line]
    width = max(len(line) for line in lines)
    bitmap: List[List[int]] = []
    for line in lines:
        # Right-pad short lines with empty cells.
        line = line.ljust(width)
        row = [1 if ch == "#" else 0 for ch in line]
        bitmap.append(row)
    # Right-trim any all-empty columns? No — keep the author's intended size.
    return bitmap


# ---- TINY (5x5) -------------------------------------------------------
_HEART = """
.#.#.
#####
#####
.###.
..#..
"""

_HOUSE = """
..#..
.###.
#####
.#.#.
.#.#.
"""

_DIAMOND = """
..#..
.###.
#####
.###.
..#..
"""

_ARROW = """
..#..
.###.
##.##
..#..
..#..
"""


# ---- EASY (8x8) -------------------------------------------------------
_FISH = """
....##..
...####.
##.#####
########
##.#####
...####.
....##..
........
"""

_KEY = """
###.....
#.#.....
###.....
.#......
.#......
.##.....
.#......
.##.#.#.
"""

_MUSHROOM = """
..####..
.######.
########
.######.
...##...
...##...
..####..
..####..
"""

_CUP = """
.######.
########
#.....##
#.....##
#.....##
########
.######.
..####..
"""


# ---- MEDIUM (10x10) ---------------------------------------------------
_SAILBOAT = """
....#.....
....##....
....###...
....####..
....#####.
##########
.########.
..######..
..........
.##.##.##.
"""

_CAT = """
##......##
###....###
##########
##.####.##
##########
##.####.##
##########
.########.
..######..
...####...
"""

_UMBRELLA = """
....##....
..######..
.########.
##########
##.##.##.#
....##....
....##....
....##....
....##....
...####...
"""


# ---- assembly ---------------------------------------------------------
def _build(id: str, title: str, art: str, difficulty: str) -> Puzzle:
    return Puzzle.from_bitmap(
        id=id, title=title, bitmap=_parse(art), difficulty=difficulty,
    )


PUZZLES: List[Puzzle] = [
    _build("heart",    "ハート",      _HEART,    "tiny"),
    _build("house",    "おうち",      _HOUSE,    "tiny"),
    _build("diamond",  "ひし形",      _DIAMOND,  "tiny"),
    _build("arrow",    "矢印",        _ARROW,    "tiny"),
    _build("fish",     "おさかな",    _FISH,     "easy"),
    _build("key",      "かぎ",        _KEY,      "easy"),
    _build("mushroom", "きのこ",      _MUSHROOM, "easy"),
    _build("cup",      "コーヒー",    _CUP,      "easy"),
    _build("sailboat", "ヨット",      _SAILBOAT, "medium"),
    _build("cat",      "ねこ",        _CAT,      "medium"),
    _build("umbrella", "あめのひ",    _UMBRELLA, "medium"),
]


_BY_ID: Dict[str, Puzzle] = {p.id: p for p in PUZZLES}


def get_puzzle(puzzle_id: str) -> Optional[Puzzle]:
    return _BY_ID.get(puzzle_id)


def list_puzzles(difficulty: Optional[str] = None) -> List[Puzzle]:
    if difficulty is None:
        return list(PUZZLES)
    return [p for p in PUZZLES if p.difficulty == difficulty]
