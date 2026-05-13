"""Tests for the domain models."""

from datetime import datetime, timezone

import pytest

from favorgame.errors import ValidationError
from favorgame.models import (
    FavorKind,
    FavorRequest,
    Notification,
    NotificationResponse,
    RequestStatus,
    SpontaneousAct,
    Transaction,
    User,
    can_request_transition,
)


class TestUser:
    def test_valid(self):
        user = User(id=1, username="alice")
        assert user.username == "alice"
        assert user.display_name == "alice"
        assert user.wallet_yen == 0
        assert user.points == 0

    def test_blank_username_rejected(self):
        with pytest.raises(ValidationError):
            User(id=1, username="   ")

    def test_negative_wallet_rejected(self):
        with pytest.raises(ValidationError):
            User(id=1, username="a", wallet_yen=-1)

    def test_roundtrip(self):
        user = User(id=7, username="bob", display_name="Bob", wallet_yen=300, points=12)
        data = user.to_dict()
        assert data["username"] == "bob"
        restored = User.from_dict(data)
        assert restored == user


class TestFavorRequest:
    def test_defaults(self):
        req = FavorRequest(
            id=1, requester_id=10, kind=FavorKind.SEAT, bounty_yen=100
        )
        assert req.kind is FavorKind.SEAT
        assert req.status is RequestStatus.OPEN
        assert req.accepter_id is None

    def test_kind_from_string(self):
        req = FavorRequest(id=1, requester_id=10, kind="seat", bounty_yen=0)
        assert req.kind is FavorKind.SEAT

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            FavorRequest(id=1, requester_id=10, kind="nope", bounty_yen=0)

    def test_generic_requires_description(self):
        with pytest.raises(ValidationError):
            FavorRequest(id=1, requester_id=10, kind=FavorKind.GENERIC, bounty_yen=0)

    def test_negative_bounty_rejected(self):
        with pytest.raises(ValidationError):
            FavorRequest(
                id=1, requester_id=10, kind=FavorKind.SEAT, bounty_yen=-1
            )

    def test_terminal(self):
        req = FavorRequest(
            id=1, requester_id=10, kind=FavorKind.SEAT, bounty_yen=0
        )
        assert not req.is_terminal()
        req.status = RequestStatus.COMPLETED
        assert req.is_terminal()


class TestRequestTransitions:
    def test_open_to_accepted_allowed(self):
        assert can_request_transition(RequestStatus.OPEN, RequestStatus.ACCEPTED)

    def test_accepted_to_completed_allowed(self):
        assert can_request_transition(RequestStatus.ACCEPTED, RequestStatus.COMPLETED)

    def test_completed_is_terminal(self):
        assert not can_request_transition(RequestStatus.COMPLETED, RequestStatus.OPEN)
        assert not can_request_transition(RequestStatus.COMPLETED, RequestStatus.ACCEPTED)

    def test_no_skip_to_completed(self):
        assert not can_request_transition(RequestStatus.OPEN, RequestStatus.COMPLETED)


class TestNotification:
    def test_respond_once(self):
        n = Notification(id=1, request_id=10, recipient_id=2)
        n.respond(NotificationResponse.ACCEPTED)
        assert n.response is NotificationResponse.ACCEPTED
        assert n.responded_at is not None

    def test_double_respond_rejected(self):
        n = Notification(id=1, request_id=10, recipient_id=2)
        n.respond(NotificationResponse.IGNORED)
        with pytest.raises(ValidationError):
            n.respond(NotificationResponse.ACCEPTED)

    def test_respond_pending_rejected(self):
        n = Notification(id=1, request_id=10, recipient_id=2)
        with pytest.raises(ValidationError):
            n.respond(NotificationResponse.PENDING)


class TestSpontaneousAct:
    def test_same_user_rejected(self):
        with pytest.raises(ValidationError):
            SpontaneousAct(
                id=1, giver_id=1, receiver_id=1, kind=FavorKind.SEAT,
                giver_delta=5, receiver_delta=-2,
            )


class TestTransaction:
    def test_negative_yen_rejected(self):
        with pytest.raises(ValidationError):
            Transaction(
                id=1, request_id=None, payer_id=1, payee_id=2,
                yen_amount=-1, point_amount=0,
            )

    def test_same_party_rejected(self):
        with pytest.raises(ValidationError):
            Transaction(
                id=1, request_id=None, payer_id=1, payee_id=1,
                yen_amount=100, point_amount=0,
            )


class TestEnumFromValue:
    def test_favor_kind_parse_passthrough(self):
        assert FavorKind.parse(FavorKind.SEAT) is FavorKind.SEAT

    def test_favor_kind_parse_unknown(self):
        with pytest.raises(ValidationError):
            FavorKind.parse("bogus")

    def test_request_status_parse(self):
        assert RequestStatus.parse("open") is RequestStatus.OPEN

    def test_notification_response_parse(self):
        assert NotificationResponse.parse("ignored") is NotificationResponse.IGNORED
