"""Tests for the RankingService."""

from favorgame.models import FavorKind


def test_leaderboard_orders_by_points_desc(populated_game):
    # Make Alice +5 (seat), Bob -2 (seat), Carol unchanged.
    populated_game.report_spontaneous(
        giver="alice", receiver="bob", kind=FavorKind.SEAT
    )
    board = populated_game.leaderboard()
    names = [e.user.username for e in board]
    points = [e.user.points for e in board]
    assert names[0] == "alice"
    assert names[-1] == "bob"
    assert points == sorted(points, reverse=True)


def test_leaderboard_ties_share_rank(populated_game):
    # Everyone stays at 0 points.
    board = populated_game.leaderboard()
    assert all(e.rank == 1 for e in board)


def test_leaderboard_dense_ranking(populated_game):
    # Alice: +5, Bob: +5 (we forge by spontaneous acts), Carol: 0
    populated_game.report_spontaneous(
        giver="alice", receiver="carol", kind=FavorKind.SEAT
    )
    populated_game.register("dave", starting_yen=0)
    populated_game.report_spontaneous(
        giver="bob", receiver="dave", kind=FavorKind.SEAT
    )
    # Now: alice=5, bob=5, dave=-2, carol=-2
    board = populated_game.leaderboard()
    ranks = {e.user.username: e.rank for e in board}
    # Alice & Bob tie at rank 1; Carol & Dave tie at rank 3.
    assert ranks["alice"] == ranks["bob"]
    assert ranks["carol"] == ranks["dave"]
    assert ranks["alice"] < ranks["carol"]


def test_leaderboard_limit(populated_game):
    board = populated_game.leaderboard(limit=2)
    assert len(board) == 2


def test_rank_of_unknown_user(populated_game):
    assert populated_game.ranking.rank_of(9999) is None
