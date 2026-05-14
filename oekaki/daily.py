"""Deterministic daily-puzzle selection.

Given a calendar date (JST) we return one specific puzzle from the
catalogue. The choice is a deterministic function of the date, so the
same date always produces the same puzzle — important for a "daily
challenge" where everyone solves the same one and can compare times.

We rotate among the *medium* puzzles by default and fall back to the
full catalogue if there aren't enough medium ones to give variety.
The rotation also tries to space difficulty across the week:

  Mon  easy
  Tue  easy
  Wed  medium
  Thu  easy
  Fri  medium
  Sat  medium
  Sun  tiny  (gentle Sunday)

Within each difficulty we pick by hash(date_iso) % len(set) so the
distribution doesn't repeat the same puzzle two days in a row even
within a small set.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from oekaki.models import Puzzle
from oekaki.puzzles import list_puzzles


JST = timezone(timedelta(hours=9))


# Difficulty for each weekday (Mon=0..Sun=6).
_BY_WEEKDAY = (
    "easy", "easy", "medium", "easy", "medium", "medium", "tiny",
)


def _hash_date(d: date) -> int:
    """A small stable hash of the ISO date string."""
    return int(hashlib.sha256(d.isoformat().encode("utf-8")).hexdigest(), 16)


def today_jst(now: Optional[datetime] = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(JST).date()


def difficulty_for(d: date) -> str:
    """Return the difficulty bucket scheduled for this date."""
    return _BY_WEEKDAY[d.weekday()]


def puzzle_for(d: date) -> Puzzle:
    """Pick the daily puzzle for ``d``.

    Falls back through difficulties if the requested bucket is empty in
    the catalogue (e.g. nothing tagged "tiny"), so we always return
    *some* puzzle.
    """
    desired = difficulty_for(d)
    fallback_order = ("tiny", "easy", "medium", "hard")
    tried: List[str] = [desired] + [d for d in fallback_order if d != desired]
    h = _hash_date(d)
    for difficulty in tried:
        pool = list_puzzles(difficulty)
        if pool:
            return pool[h % len(pool)]
    # Last-resort: the whole catalogue must be non-empty.
    pool = list_puzzles(None)
    if not pool:
        raise RuntimeError("no puzzles in catalogue")
    return pool[h % len(pool)]


def today_puzzle(now: Optional[datetime] = None) -> Puzzle:
    return puzzle_for(today_jst(now))
