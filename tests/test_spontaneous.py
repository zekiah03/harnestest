"""Tests for the spontaneous-act service."""

import pytest

from favorgame.errors import NotRegisteredError, ValidationError
from favorgame.models import FavorKind


def test_seat_given_moves_points(populated_game):
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    populated_game.report_spontaneous(
        giver="alice", receiver="bob", kind=FavorKind.SEAT
    )
    # giver gains, receiver loses.
    assert alice.points == 5
    assert bob.points == -2


def test_luggage_gives_more_than_seat(populated_game):
    populated_game.report_spontaneous(
        giver="alice", receiver="bob", kind=FavorKind.SEAT
    )
    populated_game.report_spontaneous(
        giver="alice", receiver="carol", kind=FavorKind.LUGGAGE
    )
    alice = populated_game.user("alice")
    # 5 (seat) + 8 (luggage) = 13
    assert alice.points == 13


def test_giver_equal_receiver_rejected(populated_game):
    with pytest.raises(ValidationError):
        populated_game.spontaneous.log(
            giver_id=1, receiver_id=1, kind=FavorKind.SEAT
        )


def test_unregistered_user_rejected(populated_game):
    with pytest.raises(NotRegisteredError):
        populated_game.spontaneous.log(
            giver_id=99, receiver_id=1, kind=FavorKind.SEAT
        )
    with pytest.raises(NotRegisteredError):
        populated_game.spontaneous.log(
            giver_id=1, receiver_id=99, kind=FavorKind.SEAT
        )


def test_act_recorded_in_repo(populated_game):
    populated_game.report_spontaneous(
        giver="alice", receiver="bob", kind=FavorKind.SEAT, note="JR山手線"
    )
    acts = populated_game.repo.list_spontaneous()
    assert len(acts) == 1
    assert acts[0].note == "JR山手線"
    assert acts[0].giver_delta == 5
    assert acts[0].receiver_delta == -2
