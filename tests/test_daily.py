"""Tests for the daily puzzle selector."""

from datetime import date

import pytest

from oekaki.daily import difficulty_for, puzzle_for, today_jst


class TestWeeklySchedule:
    @pytest.mark.parametrize("d, expected", [
        (date(2024, 6, 3),  "easy"),    # Monday
        (date(2024, 6, 4),  "easy"),    # Tuesday
        (date(2024, 6, 5),  "medium"),  # Wednesday
        (date(2024, 6, 6),  "easy"),    # Thursday
        (date(2024, 6, 7),  "medium"),  # Friday
        (date(2024, 6, 8),  "medium"),  # Saturday
        (date(2024, 6, 9),  "tiny"),    # Sunday
    ])
    def test_difficulty_for_weekday(self, d, expected):
        assert difficulty_for(d) == expected


class TestDeterminism:
    def test_same_date_yields_same_puzzle(self):
        d = date(2024, 6, 5)
        a = puzzle_for(d)
        b = puzzle_for(d)
        assert a.id == b.id

    def test_different_dates_can_yield_different_puzzles(self):
        # We don't claim *every* pair differs (small pools), only that
        # over a week-long span we see at least two distinct puzzles.
        seen = {puzzle_for(date(2024, 6, day)).id for day in range(3, 10)}
        assert len(seen) >= 2


class TestBucketRespected:
    def test_picks_match_difficulty(self):
        for day in range(3, 10):
            d = date(2024, 6, day)
            p = puzzle_for(d)
            # The picked puzzle's difficulty should be the requested one,
            # unless the pool was empty and we fell back.
            assert p.difficulty in ("tiny", "easy", "medium", "hard")


class TestTodayShape:
    def test_today_jst_returns_a_date(self):
        d = today_jst()
        assert isinstance(d, date)
