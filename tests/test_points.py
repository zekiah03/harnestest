"""Tests for the point-rules module."""

import pytest

from favorgame.models import FavorKind
from favorgame.points import (
    points_for_bounty,
    requester_penalty,
    reward_for_spontaneous,
)


def test_seat_reward():
    r = reward_for_spontaneous(FavorKind.SEAT)
    assert r.giver_delta > 0
    assert r.receiver_delta < 0


def test_luggage_more_rewarding_than_seat():
    seat = reward_for_spontaneous(FavorKind.SEAT)
    luggage = reward_for_spontaneous(FavorKind.LUGGAGE)
    assert luggage.giver_delta > seat.giver_delta


def test_child_watch_is_most_rewarding():
    rewards = {k: reward_for_spontaneous(k) for k in FavorKind}
    best = max(rewards.values(), key=lambda r: r.giver_delta)
    assert best == rewards[FavorKind.CHILD_WATCH]


def test_points_for_bounty_proportional():
    assert points_for_bounty(0) == 0
    assert points_for_bounty(100) == 10
    assert points_for_bounty(1000) == 100


def test_points_for_negative_bounty_rejected():
    with pytest.raises(ValueError):
        points_for_bounty(-1)


def test_requester_penalty_is_positive():
    assert requester_penalty() >= 1
