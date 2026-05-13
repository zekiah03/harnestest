"""Tests for time-of-day multipliers."""

from datetime import datetime, timedelta, timezone

import pytest

from favorgame.models import FavorKind
from favorgame.multipliers import (
    JST,
    Multiplier,
    SCHEDULE,
    active_multipliers,
    multiplier_for,
)


pytestmark = pytest.mark.multipliers  # opt back into the live SCHEDULE


def _at(year, month, day, hour, *, jst=True) -> datetime:
    """Construct a UTC datetime corresponding to a JST clock reading."""
    if jst:
        local = datetime(year, month, day, hour, tzinfo=JST)
        return local.astimezone(timezone.utc)
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


class TestMorningRush:
    def test_monday_8am_jst_doubles_seat(self):
        # 2024-01-01 was a Monday in JST.
        now = _at(2024, 1, 1, 8)
        factor, source = multiplier_for(FavorKind.SEAT, now)
        assert factor == 2.0
        assert source is not None
        assert source.reason == "朝ラッシュ"

    def test_saturday_8am_does_not_double_seat(self):
        # 2024-01-06 was a Saturday.
        now = _at(2024, 1, 6, 8)
        factor, _ = multiplier_for(FavorKind.SEAT, now)
        assert factor == 1.0

    def test_midnight_does_not_double_seat(self):
        now = _at(2024, 1, 2, 0)
        factor, _ = multiplier_for(FavorKind.SEAT, now)
        assert factor == 1.0


class TestEveningRush:
    def test_weekday_18_doubles_seat(self):
        now = _at(2024, 1, 2, 18)
        factor, source = multiplier_for(FavorKind.SEAT, now)
        assert factor == 2.0
        assert source.reason == "夕ラッシュ"


class TestLateNightLuggage:
    def test_2330_jst_boost_luggage(self):
        now = _at(2024, 1, 1, 23)
        factor, source = multiplier_for(FavorKind.LUGGAGE, now)
        assert factor == 1.5
        assert source.reason == "深夜便"

    def test_0100_jst_still_boost(self):
        # 1am wraps past midnight.
        now = _at(2024, 1, 2, 1)
        factor, _ = multiplier_for(FavorKind.LUGGAGE, now)
        assert factor == 1.5

    def test_0300_jst_no_boost(self):
        now = _at(2024, 1, 2, 3)
        factor, _ = multiplier_for(FavorKind.LUGGAGE, now)
        assert factor == 1.0


class TestWeekendChild:
    def test_sunday_afternoon_doubles_child(self):
        # 2024-01-07 was a Sunday.
        now = _at(2024, 1, 7, 14)
        factor, source = multiplier_for(FavorKind.CHILD_WATCH, now)
        assert factor == 2.0
        assert source.reason == "週末"

    def test_tuesday_does_not_boost_child(self):
        now = _at(2024, 1, 2, 14)
        factor, _ = multiplier_for(FavorKind.CHILD_WATCH, now)
        assert factor == 1.0


class TestActiveStrip:
    def test_active_multipliers_returns_winning_set_for_monday_8(self):
        now = _at(2024, 1, 1, 8)
        active = active_multipliers(now)
        kinds = {m.kind for m in active}
        # Morning rush is active for SEAT.
        assert FavorKind.SEAT in kinds

    def test_active_multipliers_can_be_empty(self):
        # Tuesday 12:00 JST — should have nothing active.
        now = _at(2024, 1, 2, 12)
        active = active_multipliers(now)
        assert active == []


class TestSpontaneousIntegration:
    """Verify the multiplier really lands on the recorded act."""

    def test_morning_rush_doubles_giver_gain(self, populated_game, monkeypatch):
        # Force a specific clock for this test.
        rush = _at(2024, 1, 1, 8)
        monkeypatch.setattr(
            "favorgame.spontaneous.multiplier_for",
            lambda kind, now=None: multiplier_for(kind, rush),
        )
        act = populated_game.report_spontaneous(
            giver="alice", receiver="bob", kind=FavorKind.SEAT
        )
        # Base seat gain is 5; doubled = 10.
        assert act.giver_delta == 10
        # Receiver loss is NOT scaled — still -2.
        assert act.receiver_delta == -2
        assert act.multiplier == 2.0
        assert act.multiplier_reason == "朝ラッシュ"

    def test_quiet_hour_keeps_base_rate(self, populated_game, monkeypatch):
        quiet = _at(2024, 1, 2, 12)
        monkeypatch.setattr(
            "favorgame.spontaneous.multiplier_for",
            lambda kind, now=None: multiplier_for(kind, quiet),
        )
        act = populated_game.report_spontaneous(
            giver="alice", receiver="bob", kind=FavorKind.SEAT
        )
        assert act.giver_delta == 5
        assert act.multiplier == 1.0
        assert act.multiplier_reason == ""
