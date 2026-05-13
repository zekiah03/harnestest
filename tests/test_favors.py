"""Tests for the paid-favor request lifecycle."""

import pytest

from favorgame.errors import (
    InsufficientFundsError,
    NotRegisteredError,
    StateError,
    ValidationError,
)
from favorgame.models import (
    FavorKind,
    NotificationResponse,
    RequestStatus,
)


def test_request_creates_open_and_escrows_yen(populated_game):
    alice = populated_game.user("alice")
    starting = alice.wallet_yen
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    assert req.status is RequestStatus.OPEN
    assert alice.wallet_yen == starting - 100


def test_request_fans_out_to_others(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    notes = populated_game.repo.list_notifications(request_id=req.id)
    recipients = {n.recipient_id for n in notes}
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    carol = populated_game.user("carol")
    assert alice.id not in recipients
    assert recipients == {bob.id, carol.id}


def test_request_with_too_little_yen_rejected(populated_game):
    with pytest.raises(InsufficientFundsError):
        populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=10_000
        )


def test_request_negative_bounty_rejected(populated_game):
    with pytest.raises(ValidationError):
        populated_game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=-1
        )


def test_accept_marks_request_and_ignores_other_notifications(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    populated_game.accept_favor(accepter="bob", request_id=req.id)
    refreshed = populated_game.repo.get_request(req.id)
    assert refreshed.status is RequestStatus.ACCEPTED
    bob = populated_game.user("bob")
    assert refreshed.accepter_id == bob.id
    # Carol's notification should now be IGNORED automatically.
    notes = populated_game.repo.list_notifications(request_id=req.id)
    carol_note = next(n for n in notes if n.recipient_id == populated_game.user("carol").id)
    assert carol_note.response is NotificationResponse.IGNORED


def test_accept_by_non_recipient_rejected(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    bob_note = populated_game.favors.find_notification_for(
        request_id=req.id, recipient_id=populated_game.user("bob").id
    )
    assert bob_note is not None
    with pytest.raises(NotRegisteredError):
        populated_game.favors.accept_request(
            notification_id=bob_note.id,
            accepter_id=populated_game.user("carol").id,
        )


def test_complete_pays_accepter(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    populated_game.accept_favor(accepter="bob", request_id=req.id)
    populated_game.complete_favor(requester="alice", request_id=req.id)
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    # Alice paid 100 yen.
    assert alice.wallet_yen == 900
    # Bob received 100 yen.
    assert bob.wallet_yen == 1100
    # Bob also gets 10 points (100 yen * 0.1).
    assert bob.points == 10
    # Alice gets the requester penalty.
    assert alice.points == -1


def test_complete_only_by_requester(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    populated_game.accept_favor(accepter="bob", request_id=req.id)
    with pytest.raises(ValidationError):
        populated_game.complete_favor(requester="bob", request_id=req.id)


def test_cannot_complete_an_open_request(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    with pytest.raises(StateError):
        populated_game.complete_favor(requester="alice", request_id=req.id)


def test_cancel_refunds_escrow(populated_game):
    starting = populated_game.user("alice").wallet_yen
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    populated_game.cancel_favor(requester="alice", request_id=req.id)
    alice = populated_game.user("alice")
    assert alice.wallet_yen == starting
    assert populated_game.repo.get_request(req.id).status is RequestStatus.CANCELLED


def test_cancel_after_accept_still_refunds(populated_game):
    starting = populated_game.user("alice").wallet_yen
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    populated_game.accept_favor(accepter="bob", request_id=req.id)
    populated_game.cancel_favor(requester="alice", request_id=req.id)
    assert populated_game.user("alice").wallet_yen == starting
    assert populated_game.user("bob").wallet_yen == 1000  # no transfer


def test_expire_refunds_and_ignores_pending(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=200
    )
    populated_game.favors.expire_request(request_id=req.id)
    refreshed = populated_game.repo.get_request(req.id)
    assert refreshed.status is RequestStatus.EXPIRED
    assert populated_game.user("alice").wallet_yen == 1000
    for n in populated_game.repo.list_notifications(request_id=req.id):
        assert n.response is NotificationResponse.IGNORED


def test_cannot_accept_own_request(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    # No notification ever went to alice; reach in to fake one.
    populated_game.repo.add_notification(
        __import__("favorgame").Notification(
            id=populated_game.repo.next_id("notification"),
            request_id=req.id,
            recipient_id=populated_game.user("alice").id,
        )
    )
    with pytest.raises(ValidationError):
        populated_game.accept_favor(accepter="alice", request_id=req.id)


def test_toilet_order_and_child_watch_supported(populated_game):
    req1 = populated_game.request_favor(
        requester="alice", kind=FavorKind.TOILET_ORDER, bounty_yen=100
    )
    req2 = populated_game.request_favor(
        requester="alice", kind=FavorKind.CHILD_WATCH, bounty_yen=200
    )
    assert req1.kind is FavorKind.TOILET_ORDER
    assert req2.kind is FavorKind.CHILD_WATCH


def test_generic_requires_description(populated_game):
    with pytest.raises(ValidationError):
        populated_game.request_favor(
            requester="alice", kind=FavorKind.GENERIC, bounty_yen=100
        )
    req = populated_game.request_favor(
        requester="alice",
        kind=FavorKind.GENERIC,
        bounty_yen=100,
        description="ペットを5分だけ見て",
    )
    assert req.kind is FavorKind.GENERIC
