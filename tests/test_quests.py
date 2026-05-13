"""Tests for the daily quest evaluator."""

from datetime import datetime, timedelta, timezone

import pytest

from favorgame.models import FavorKind, FavorRequest, RequestStatus, SpontaneousAct
from favorgame.multipliers import JST
from favorgame.quests import QUESTS, evaluate_for


def _jst_today_dt(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=JST).astimezone(timezone.utc)


def _drop_act(repo, giver, receiver, kind, when):
    repo.add_spontaneous(SpontaneousAct(
        id=repo.next_id("spontaneous"),
        giver_id=giver.id, receiver_id=receiver.id, kind=kind,
        giver_delta=5, receiver_delta=-2, created_at=when,
    ))


def _status(statuses, quest_id):
    return next(s for s in statuses if s.quest.id == quest_id)


class TestVariety:
    def test_three_distinct_kinds_completes_variety(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        for k in (FavorKind.SEAT, FavorKind.LUGGAGE, FavorKind.TOILET_ORDER):
            _drop_act(populated_game.repo, alice, bob, k, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "variety_3")
        assert s.progress == 3
        assert s.completed

    def test_two_kinds_partial(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice, bob, FavorKind.SEAT, now)
        _drop_act(populated_game.repo, alice, bob, FavorKind.LUGGAGE, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "variety_3")
        assert s.progress == 2
        assert not s.completed

    def test_repeated_kind_doesnt_double_count(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        for _ in range(3):
            _drop_act(populated_game.repo, alice, bob, FavorKind.SEAT, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "variety_3")
        assert s.progress == 1

    def test_yesterday_acts_ignored(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        for k in (FavorKind.SEAT, FavorKind.LUGGAGE, FavorKind.TOILET_ORDER):
            _drop_act(populated_game.repo, alice, bob, k, now - timedelta(days=1))
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "variety_3")
        assert s.progress == 0


class TestHelped:
    def test_two_distinct_recipients_completes_helped(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        carol = populated_game.user("carol")
        now = _jst_today_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice, bob, FavorKind.SEAT, now)
        _drop_act(populated_game.repo, alice, carol, FavorKind.LUGGAGE, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "helped_2")
        assert s.progress == 2
        assert s.completed

    def test_helping_same_person_twice_is_one(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        _drop_act(populated_game.repo, alice, bob, FavorKind.SEAT, now)
        _drop_act(populated_game.repo, alice, bob, FavorKind.LUGGAGE, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "helped_2")
        assert s.progress == 1


class TestClosed:
    def test_completing_a_paid_request_today_counts(self, populated_game):
        req = populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        populated_game.accept_favor(accepter="bob", request_id=req.id)
        populated_game.complete_favor(requester="alice", request_id=req.id)
        # Both alice (requester) and bob (accepter) should see 1/1.
        now = datetime.now(timezone.utc)
        for username in ("alice", "bob"):
            u = populated_game.user(username)
            s = _status(evaluate_for(u, populated_game.repo, now=now), "closed_1")
            assert s.progress == 1, username
            assert s.completed

    def test_open_request_does_not_count(self, populated_game):
        populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        now = datetime.now(timezone.utc)
        s = _status(evaluate_for(populated_game.user("alice"),
                                 populated_game.repo, now=now), "closed_1")
        assert s.progress == 0


class TestRoster:
    def test_all_three_quests_have_evaluators(self, populated_game):
        # If a quest id has no evaluator, evaluate_for would raise.
        evaluate_for(populated_game.user("alice"), populated_game.repo)

    def test_quest_ids_unique(self):
        ids = [q.id for q in QUESTS]
        assert len(set(ids)) == len(ids)


class TestStatusDict:
    def test_completed_percent_is_100(self, populated_game):
        alice = populated_game.user("alice")
        bob = populated_game.user("bob")
        now = _jst_today_dt(2024, 6, 5, 14)
        for k in (FavorKind.SEAT, FavorKind.LUGGAGE, FavorKind.TOILET_ORDER):
            _drop_act(populated_game.repo, alice, bob, k, now)
        s = _status(evaluate_for(alice, populated_game.repo, now=now), "variety_3")
        assert s.to_dict()["percent"] == 100
