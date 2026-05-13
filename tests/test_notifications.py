"""Tests for the NotificationService."""

import pytest

from favorgame.errors import ValidationError
from favorgame.models import FavorKind, NotificationResponse, RequestStatus


def test_fan_out_excludes_requester(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    notes = populated_game.repo.list_notifications(request_id=req.id)
    alice = populated_game.user("alice")
    assert alice.id not in {n.recipient_id for n in notes}
    assert all(n.response is NotificationResponse.PENDING for n in notes)


def test_inbox_only_returns_pending(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    # bob ignores
    bob_id = populated_game.user("bob").id
    bob_note = populated_game.favors.find_notification_for(
        request_id=req.id, recipient_id=bob_id
    )
    assert bob_note is not None
    populated_game.notifications.ignore(bob_note.id)

    bob_inbox = populated_game.inbox("bob")
    carol_inbox = populated_game.inbox("carol")
    assert bob_inbox == []
    assert len(carol_inbox) == 1


def test_double_response_blocked(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    bob_id = populated_game.user("bob").id
    note = populated_game.favors.find_notification_for(
        request_id=req.id, recipient_id=bob_id
    )
    populated_game.notifications.ignore(note.id)
    with pytest.raises(ValidationError):
        populated_game.notifications.ignore(note.id)


def test_fan_out_on_terminal_request_rejected(populated_game):
    req = populated_game.request_favor(
        requester="alice", kind=FavorKind.SEAT, bounty_yen=100
    )
    req.status = RequestStatus.COMPLETED
    from favorgame.errors import StateError

    with pytest.raises(StateError):
        populated_game.notifications.fan_out(req)
