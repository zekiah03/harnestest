"""Domain models for FavorGame.

Plain dataclasses with light validation. They know how to serialize themselves
to / from JSON-friendly dicts so the repository layer can stay thin.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from favorgame.errors import ValidationError


def utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime`` for ``now``."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class FavorKind(str, Enum):
    """A taxonomy of paid favors and spontaneous acts."""

    SEAT = "seat"             # 席を譲る / 譲ってほしい
    LUGGAGE = "luggage"       # 荷物を持つ / 持ってほしい
    TOILET_ORDER = "toilet"   # トイレの順番を譲る / 譲ってほしい
    CHILD_WATCH = "child"     # 一時的に子供を見てほしい
    GENERIC = "generic"       # その他

    @classmethod
    def parse(cls, value: Any) -> "FavorKind":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValidationError(f"unknown favor kind: {value!r}") from exc


class RequestStatus(str, Enum):
    OPEN = "open"               # 通知中、まだ承認者なし
    ACCEPTED = "accepted"       # 誰かが承認した
    COMPLETED = "completed"     # 完了 — 金と点が動いた
    CANCELLED = "cancelled"     # 依頼者がキャンセル
    EXPIRED = "expired"         # 締め切り切れ

    @classmethod
    def parse(cls, value: Any) -> "RequestStatus":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValidationError(f"unknown status: {value!r}") from exc


class NotificationResponse(str, Enum):
    PENDING = "pending"
    IGNORED = "ignored"
    ACCEPTED = "accepted"

    @classmethod
    def parse(cls, value: Any) -> "NotificationResponse":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValidationError(f"unknown response: {value!r}") from exc


# Allowed transitions for a FavorRequest. Terminal states have empty sets.
_REQUEST_TRANSITIONS: Dict[RequestStatus, set] = {
    RequestStatus.OPEN: {RequestStatus.ACCEPTED, RequestStatus.CANCELLED, RequestStatus.EXPIRED},
    RequestStatus.ACCEPTED: {RequestStatus.COMPLETED, RequestStatus.CANCELLED},
    RequestStatus.COMPLETED: set(),
    RequestStatus.CANCELLED: set(),
    RequestStatus.EXPIRED: set(),
}


def can_request_transition(current: RequestStatus, target: RequestStatus) -> bool:
    if current is target:
        return False
    return target in _REQUEST_TRANSITIONS[current]


@dataclass
class User:
    """A registered user. Only registered users may transact with each other."""

    id: int
    username: str
    display_name: str = ""
    wallet_yen: int = 0
    points: int = 0
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.username or not self.username.strip():
            raise ValidationError("username must not be empty")
        if self.wallet_yen < 0:
            raise ValidationError(f"wallet_yen must be >= 0, got {self.wallet_yen}")
        if not self.display_name:
            self.display_name = self.username

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _iso(self.created_at)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            id=int(data["id"]),
            username=data["username"],
            display_name=data.get("display_name", ""),
            wallet_yen=int(data.get("wallet_yen", 0)),
            points=int(data.get("points", 0)),
            created_at=_parse_iso(data["created_at"]),
        )


@dataclass
class FavorRequest:
    """A paid request broadcast to other registered users.

    The bounty is in yen and is escrowed off the requester's wallet when the
    request opens; it is released to the accepter on completion (or refunded
    on cancel / expiry).
    """

    id: int
    requester_id: int
    kind: FavorKind
    bounty_yen: int
    description: str = ""
    status: RequestStatus = RequestStatus.OPEN
    accepter_id: Optional[int] = None
    created_at: datetime = field(default_factory=utcnow)
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.kind = FavorKind.parse(self.kind)
        self.status = RequestStatus.parse(self.status)
        if self.bounty_yen < 0:
            raise ValidationError(f"bounty_yen must be >= 0, got {self.bounty_yen}")
        if not self.description and self.kind is FavorKind.GENERIC:
            raise ValidationError("generic favors require a description")

    def is_terminal(self) -> bool:
        return self.status in (
            RequestStatus.COMPLETED,
            RequestStatus.CANCELLED,
            RequestStatus.EXPIRED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "requester_id": self.requester_id,
            "kind": self.kind.value,
            "bounty_yen": self.bounty_yen,
            "description": self.description,
            "status": self.status.value,
            "accepter_id": self.accepter_id,
            "created_at": _iso(self.created_at),
            "accepted_at": _iso(self.accepted_at) if self.accepted_at else None,
            "completed_at": _iso(self.completed_at) if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FavorRequest":
        return cls(
            id=int(data["id"]),
            requester_id=int(data["requester_id"]),
            kind=FavorKind.parse(data["kind"]),
            bounty_yen=int(data["bounty_yen"]),
            description=data.get("description", ""),
            status=RequestStatus.parse(data.get("status", RequestStatus.OPEN.value)),
            accepter_id=data.get("accepter_id"),
            created_at=_parse_iso(data["created_at"]),
            accepted_at=_parse_iso(data["accepted_at"]) if data.get("accepted_at") else None,
            completed_at=_parse_iso(data["completed_at"]) if data.get("completed_at") else None,
        )


@dataclass
class Notification:
    """A push notification sent to a single registered user for a request."""

    id: int
    request_id: int
    recipient_id: int
    response: NotificationResponse = NotificationResponse.PENDING
    created_at: datetime = field(default_factory=utcnow)
    responded_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.response = NotificationResponse.parse(self.response)

    def respond(self, response: NotificationResponse) -> None:
        response = NotificationResponse.parse(response)
        if response is NotificationResponse.PENDING:
            raise ValidationError("cannot respond with PENDING")
        if self.response is not NotificationResponse.PENDING:
            raise ValidationError(
                f"notification already responded ({self.response.value})"
            )
        self.response = response
        self.responded_at = utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "recipient_id": self.recipient_id,
            "response": self.response.value,
            "created_at": _iso(self.created_at),
            "responded_at": _iso(self.responded_at) if self.responded_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        return cls(
            id=int(data["id"]),
            request_id=int(data["request_id"]),
            recipient_id=int(data["recipient_id"]),
            response=NotificationResponse.parse(
                data.get("response", NotificationResponse.PENDING.value)
            ),
            created_at=_parse_iso(data["created_at"]),
            responded_at=_parse_iso(data["responded_at"]) if data.get("responded_at") else None,
        )


@dataclass
class SpontaneousAct:
    """A self-reported kind act between two registered users (no money).

    Per the spec the *giver* gains points and the *receiver* loses points —
    this models the "if you let someone give up their seat for you, your
    score goes down" reciprocity rule.
    """

    id: int
    giver_id: int
    receiver_id: int
    kind: FavorKind
    note: str = ""
    giver_delta: int = 0
    receiver_delta: int = 0
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.kind = FavorKind.parse(self.kind)
        if self.giver_id == self.receiver_id:
            raise ValidationError("giver and receiver must differ")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "giver_id": self.giver_id,
            "receiver_id": self.receiver_id,
            "kind": self.kind.value,
            "note": self.note,
            "giver_delta": self.giver_delta,
            "receiver_delta": self.receiver_delta,
            "created_at": _iso(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpontaneousAct":
        return cls(
            id=int(data["id"]),
            giver_id=int(data["giver_id"]),
            receiver_id=int(data["receiver_id"]),
            kind=FavorKind.parse(data["kind"]),
            note=data.get("note", ""),
            giver_delta=int(data.get("giver_delta", 0)),
            receiver_delta=int(data.get("receiver_delta", 0)),
            created_at=_parse_iso(data["created_at"]),
        )


@dataclass
class Transaction:
    """A double-entry ledger row. Amounts are signed for the wallet column."""

    id: int
    request_id: Optional[int]
    payer_id: int
    payee_id: int
    yen_amount: int
    point_amount: int
    memo: str = ""
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.yen_amount < 0:
            raise ValidationError("yen_amount must be >= 0")
        if self.payer_id == self.payee_id:
            raise ValidationError("payer and payee must differ")

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["created_at"] = _iso(self.created_at)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            id=int(data["id"]),
            request_id=data.get("request_id"),
            payer_id=int(data["payer_id"]),
            payee_id=int(data["payee_id"]),
            yen_amount=int(data["yen_amount"]),
            point_amount=int(data["point_amount"]),
            memo=data.get("memo", ""),
            created_at=_parse_iso(data["created_at"]),
        )
