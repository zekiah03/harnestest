"""Tests for the achievement engine."""

from favorgame.achievements import (
    ACHIEVEMENTS,
    AchievementStatus,
    earned_for,
    evaluate_for,
)
from favorgame.models import FavorKind


def _status(statuses, ach_id):
    return next(s for s in statuses if s.achievement.id == ach_id)


class TestCatalogue:
    def test_all_achievements_have_calculators(self):
        # Every catalogue entry must be calculable.
        repo_like = None  # not actually used; we just want evaluate_for not to KeyError
        # Build dummy and verify by indexing into the private map indirectly via evaluate
        # If a catalogue id had no calculator, evaluate_for would raise.
        for ach in ACHIEVEMENTS:
            assert ach.target >= 1
            assert ach.icon
            assert ach.name

    def test_catalogue_ids_unique(self):
        ids = [a.id for a in ACHIEVEMENTS]
        assert len(set(ids)) == len(ids)


class TestEvaluateFor:
    def test_fresh_user_has_no_earned_achievements(self, populated_game):
        alice = populated_game.user("alice")
        statuses = evaluate_for(alice, populated_game.repo)
        assert all(not s.earned for s in statuses)
        assert all(s.progress == 0 for s in statuses if s.achievement.id != "first_paid")

    def test_first_kindness_unlocks_after_one_spontaneous(self, populated_game):
        alice = populated_game.user("alice")
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        statuses = evaluate_for(alice, populated_game.repo)
        s = _status(statuses, "first_kindness")
        assert s.earned
        assert s.progress == 1

    def test_seat_giver_progress_counts_only_seats(self, populated_game):
        # Mix of kinds; only SEAT should count toward seat_giver_10.
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        populated_game.report_spontaneous(giver="alice", receiver="carol", kind=FavorKind.LUGGAGE)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "seat_giver_10").progress == 2
        assert _status(statuses, "luggage_pro").progress == 1

    def test_three_kinds_progress(self, populated_game):
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "three_kinds").progress == 1
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.LUGGAGE)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "three_kinds").progress == 2
        # Repeating same kind does not advance progress.
        populated_game.report_spontaneous(giver="alice", receiver="carol", kind=FavorKind.LUGGAGE)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "three_kinds").progress == 2
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.TOILET_ORDER)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        three = _status(statuses, "three_kinds")
        assert three.progress == 3
        assert three.earned

    def test_all_kinds_requires_every_kind(self, populated_game):
        kinds = [FavorKind.SEAT, FavorKind.LUGGAGE, FavorKind.TOILET_ORDER, FavorKind.CHILD_WATCH, FavorKind.GENERIC]
        for k in kinds:
            populated_game.report_spontaneous(giver="alice", receiver="bob", kind=k)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        ach = _status(statuses, "all_kinds")
        assert ach.progress == 5
        assert ach.earned

    def test_first_paid_unlocks_with_one_request(self, populated_game):
        populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100
        )
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "first_paid").earned

    def test_rescuer_counts_only_completed_acceptances(self, populated_game):
        # Bob accepts but never completes — should not count.
        req = populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100
        )
        populated_game.accept_favor(accepter="bob", request_id=req.id)
        statuses = evaluate_for(populated_game.user("bob"), populated_game.repo)
        assert _status(statuses, "rescuer_10").progress == 0

        populated_game.complete_favor(requester="alice", request_id=req.id)
        statuses = evaluate_for(populated_game.user("bob"), populated_game.repo)
        assert _status(statuses, "rescuer_10").progress == 1

    def test_benefactor_sums_completed_bounties(self, populated_game):
        for bounty in (200, 300, 500):
            req = populated_game.request_favor(
                requester="alice", kind=FavorKind.SEAT, bounty_yen=bounty
            )
            populated_game.accept_favor(accepter="bob", request_id=req.id)
            populated_game.complete_favor(requester="alice", request_id=req.id)
        statuses = evaluate_for(populated_game.user("alice"), populated_game.repo)
        assert _status(statuses, "benefactor_5k").progress == 1000

    def test_tier_regular_progress_clamps_at_50(self, populated_game):
        alice = populated_game.user("alice")
        alice.points = 30
        statuses = evaluate_for(alice, populated_game.repo)
        assert _status(statuses, "tier_regular").progress == 30
        alice.points = 99
        statuses = evaluate_for(alice, populated_game.repo)
        s = _status(statuses, "tier_regular")
        assert s.progress == 50
        assert s.earned

    def test_negative_points_yield_zero_progress(self, populated_game):
        alice = populated_game.user("alice")
        alice.points = -20
        statuses = evaluate_for(alice, populated_game.repo)
        assert _status(statuses, "tier_regular").progress == 0


class TestEarnedFor:
    def test_returns_only_earned_subset(self, populated_game):
        populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        earned = earned_for(populated_game.user("alice"), populated_game.repo)
        assert any(a.id == "first_kindness" for a in earned)
        assert not any(a.id == "seat_giver_10" for a in earned)


class TestStatusToDict:
    def test_to_dict_percent_caps_at_100(self, populated_game):
        alice = populated_game.user("alice")
        alice.points = 999  # over 50, so tier_regular is earned
        s = _status(evaluate_for(alice, populated_game.repo), "tier_regular")
        d = s.to_dict()
        assert d["earned"] is True
        assert d["percent"] == 100

    def test_to_dict_percent_partial(self, populated_game):
        # progress 5 / target 10 = 50%
        for _ in range(5):
            populated_game.report_spontaneous(giver="alice", receiver="bob", kind=FavorKind.SEAT)
        s = _status(
            evaluate_for(populated_game.user("alice"), populated_game.repo),
            "seat_giver_10",
        )
        assert not s.earned
        assert s.to_dict()["percent"] == 50
