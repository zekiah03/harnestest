"""Tests for the daily-streak computation."""

from datetime import datetime, timedelta, timezone

import pytest

from favorgame.models import FavorKind, SpontaneousAct
from favorgame.multipliers import JST
from favorgame.streaks import streak_for


def _jst_dt(year, month, day, hour=12):
    """Build a UTC datetime for the given JST clock."""
    return datetime(year, month, day, hour, tzinfo=JST).astimezone(timezone.utc)


def _drop_act(repo, giver_id, receiver_id, created_at):
    """Inject a spontaneous act with a controlled timestamp."""
    repo.add_spontaneous(SpontaneousAct(
        id=repo.next_id("spontaneous"),
        giver_id=giver_id, receiver_id=receiver_id,
        kind=FavorKind.SEAT,
        giver_delta=5, receiver_delta=-2,
        created_at=created_at,
    ))


class TestNoActivity:
    def test_zero_when_user_has_no_history(self, populated_game):
        now = _jst_dt(2024, 6, 1)
        s = streak_for(populated_game.user("alice"), populated_game.repo, now=now)
        assert s.current == 0
        assert s.longest == 0
        assert s.last_active is None


class TestActiveToday:
    def test_just_today_yields_one(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice.id, bob.id, now)
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 1
        assert s.longest == 1

    def test_today_plus_yesterday_yields_two(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice.id, bob.id, now - timedelta(days=1))
        _drop_act(populated_game.repo, alice.id, bob.id, now)
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 2

    def test_long_unbroken_run(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 10, 14)
        for offset in range(7):
            _drop_act(populated_game.repo, alice.id, bob.id, now - timedelta(days=offset))
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 7
        assert s.longest == 7


class TestGrace:
    def test_yesterday_active_today_silent_still_counts(self, populated_game):
        """User has until JST midnight tomorrow to keep the streak alive."""
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 5, 8)
        _drop_act(populated_game.repo, alice.id, bob.id, now - timedelta(days=1))
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 1

    def test_two_day_gap_breaks_streak(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice.id, bob.id, now - timedelta(days=2))
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 0


class TestLongestVsCurrent:
    def test_longest_remembers_past_run_even_when_broken(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 20, 14)
        # 5-day run in the distant past.
        for offset in range(5):
            _drop_act(populated_game.repo, alice.id, bob.id,
                      _jst_dt(2024, 6, 1) - timedelta(days=offset))
        # Today, a single act.
        _drop_act(populated_game.repo, alice.id, bob.id, now)
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.current == 1
        assert s.longest == 5


class TestTransactionCounts:
    def test_paid_favor_completion_counts_for_both_parties(self, populated_game):
        # Set up a completed paid request — Carol pays Bob.
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        carol = populated_game.user("carol")
        req = populated_game.request_favor(
            requester="carol", kind=FavorKind.TOILET_ORDER, bounty_yen=100,
        )
        populated_game.accept_favor(accepter="bob", request_id=req.id)
        populated_game.complete_favor(requester="carol", request_id=req.id)
        # Both Carol and Bob should have a streak of 1 today.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for u in (bob, carol):
            s = streak_for(u, populated_game.repo, now=now)
            assert s.current >= 1, f"{u.username} streak was {s.current}"
        # Alice was not party to the transaction.
        assert streak_for(alice, populated_game.repo, now=now).current == 0


class TestLastActiveSurfacing:
    def test_iso_date_format(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice.id, bob.id, now)
        s = streak_for(alice, populated_game.repo, now=now)
        assert s.last_active == "2024-06-05"
