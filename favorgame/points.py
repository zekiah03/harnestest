"""Point rules.

Spontaneous (no money) acts move points from receiver to giver. Paid
favors (a FavorRequest that someone accepted) move yen from requester to
accepter and also give the accepter a bonus point award proportional to the
bounty.
"""

from __future__ import annotations

from dataclasses import dataclass

from favorgame.models import FavorKind


@dataclass(frozen=True)
class SpontaneousReward:
    giver_delta: int
    receiver_delta: int


# Per-kind reward for a self-reported good deed where no money changes hands.
# Receiver loses fewer points than the giver gains — the system is net positive
# but still penalises being the type of person who routinely *receives* favors
# without reciprocating.
_SPONTANEOUS_REWARDS: dict[FavorKind, SpontaneousReward] = {
    FavorKind.SEAT: SpontaneousReward(giver_delta=5, receiver_delta=-2),
    FavorKind.LUGGAGE: SpontaneousReward(giver_delta=8, receiver_delta=-3),
    FavorKind.TOILET_ORDER: SpontaneousReward(giver_delta=3, receiver_delta=-1),
    FavorKind.CHILD_WATCH: SpontaneousReward(giver_delta=15, receiver_delta=-5),
    FavorKind.GENERIC: SpontaneousReward(giver_delta=2, receiver_delta=-1),
}


def reward_for_spontaneous(kind: FavorKind) -> SpontaneousReward:
    """Return the point movement for an unsolicited kind act."""
    return _SPONTANEOUS_REWARDS[FavorKind.parse(kind)]


# Each yen of bounty also yields this many bonus reputation points when the
# request completes. Tuned so that a 100-yen seat swap yields ~10 points.
_POINTS_PER_YEN: float = 0.1


def points_for_bounty(bounty_yen: int) -> int:
    """Convert a yen bounty into a non-negative bonus point amount."""
    if bounty_yen < 0:
        raise ValueError("bounty must be non-negative")
    return int(bounty_yen * _POINTS_PER_YEN)


# When a request completes, the requester also loses a small amount of
# reputation — paying for help shouldn't be quite as good as helping back.
_REQUESTER_PENALTY: int = 1


def requester_penalty() -> int:
    return _REQUESTER_PENALTY
