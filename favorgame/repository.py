"""JSON-backed repository for FavorGame entities.

Keeps every collection in memory and atomically rewrites a single JSON file
on each ``save()``. This is fine for a CLI and dirt-cheap to test against.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from favorgame.errors import DuplicateError, NotFoundError
from favorgame.models import (
    FavorRequest,
    Notification,
    SpontaneousAct,
    Transaction,
    User,
)


_SCHEMA_VERSION = 1


class Repository:
    """A simple JSON document store.

    The store is keyed by entity type. Ids are auto-incremented per type.
    Pass ``path=None`` to operate purely in memory (useful for tests).
    """

    def __init__(self, path: Optional[os.PathLike] = None) -> None:
        self.path: Optional[Path] = Path(path) if path else None
        self._users: Dict[int, User] = {}
        self._username_index: Dict[str, int] = {}
        self._requests: Dict[int, FavorRequest] = {}
        self._notifications: Dict[int, Notification] = {}
        self._spontaneous: Dict[int, SpontaneousAct] = {}
        self._transactions: Dict[int, Transaction] = {}
        self._next_ids: Dict[str, int] = {
            "user": 1,
            "request": 1,
            "notification": 1,
            "spontaneous": 1,
            "transaction": 1,
        }
        if self.path and self.path.exists():
            self.load()

    # ------------------------------------------------------------------
    # id helpers
    # ------------------------------------------------------------------
    def next_id(self, kind: str) -> int:
        if kind not in self._next_ids:
            raise KeyError(f"unknown id sequence: {kind}")
        value = self._next_ids[kind]
        self._next_ids[kind] = value + 1
        return value

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    def add_user(self, user: User) -> User:
        if user.id in self._users:
            raise DuplicateError(f"user id {user.id} already exists")
        if user.username in self._username_index:
            raise DuplicateError(f"username {user.username!r} already taken")
        self._users[user.id] = user
        self._username_index[user.username] = user.id
        if user.id >= self._next_ids["user"]:
            self._next_ids["user"] = user.id + 1
        return user

    def get_user(self, user_id: int) -> User:
        try:
            return self._users[user_id]
        except KeyError as exc:
            raise NotFoundError(f"user {user_id} not found") from exc

    def get_user_by_username(self, username: str) -> User:
        try:
            return self._users[self._username_index[username]]
        except KeyError as exc:
            raise NotFoundError(f"user {username!r} not found") from exc

    def has_user(self, user_id: int) -> bool:
        return user_id in self._users

    def list_users(self) -> List[User]:
        return list(self._users.values())

    # ------------------------------------------------------------------
    # favor requests
    # ------------------------------------------------------------------
    def add_request(self, request: FavorRequest) -> FavorRequest:
        if request.id in self._requests:
            raise DuplicateError(f"request id {request.id} already exists")
        self._requests[request.id] = request
        if request.id >= self._next_ids["request"]:
            self._next_ids["request"] = request.id + 1
        return request

    def get_request(self, request_id: int) -> FavorRequest:
        try:
            return self._requests[request_id]
        except KeyError as exc:
            raise NotFoundError(f"request {request_id} not found") from exc

    def list_requests(self) -> List[FavorRequest]:
        return list(self._requests.values())

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    def add_notification(self, notification: Notification) -> Notification:
        if notification.id in self._notifications:
            raise DuplicateError(f"notification id {notification.id} already exists")
        self._notifications[notification.id] = notification
        if notification.id >= self._next_ids["notification"]:
            self._next_ids["notification"] = notification.id + 1
        return notification

    def get_notification(self, notification_id: int) -> Notification:
        try:
            return self._notifications[notification_id]
        except KeyError as exc:
            raise NotFoundError(f"notification {notification_id} not found") from exc

    def list_notifications(
        self,
        *,
        recipient_id: Optional[int] = None,
        request_id: Optional[int] = None,
    ) -> List[Notification]:
        items: Iterable[Notification] = self._notifications.values()
        if recipient_id is not None:
            items = (n for n in items if n.recipient_id == recipient_id)
        if request_id is not None:
            items = (n for n in items if n.request_id == request_id)
        return list(items)

    # ------------------------------------------------------------------
    # spontaneous acts
    # ------------------------------------------------------------------
    def add_spontaneous(self, act: SpontaneousAct) -> SpontaneousAct:
        if act.id in self._spontaneous:
            raise DuplicateError(f"spontaneous id {act.id} already exists")
        self._spontaneous[act.id] = act
        if act.id >= self._next_ids["spontaneous"]:
            self._next_ids["spontaneous"] = act.id + 1
        return act

    def list_spontaneous(self) -> List[SpontaneousAct]:
        return list(self._spontaneous.values())

    # ------------------------------------------------------------------
    # transactions
    # ------------------------------------------------------------------
    def add_transaction(self, tx: Transaction) -> Transaction:
        if tx.id in self._transactions:
            raise DuplicateError(f"transaction id {tx.id} already exists")
        self._transactions[tx.id] = tx
        if tx.id >= self._next_ids["transaction"]:
            self._next_ids["transaction"] = tx.id + 1
        return tx

    def list_transactions(self) -> List[Transaction]:
        return list(self._transactions.values())

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": _SCHEMA_VERSION,
            "next_ids": dict(self._next_ids),
            "users": [u.to_dict() for u in self._users.values()],
            "requests": [r.to_dict() for r in self._requests.values()],
            "notifications": [n.to_dict() for n in self._notifications.values()],
            "spontaneous": [a.to_dict() for a in self._spontaneous.values()],
            "transactions": [t.to_dict() for t in self._transactions.values()],
        }

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        # Atomic write: tmp file in same dir, then rename.
        fd, tmp_path = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return
        data = json.loads(raw)
        # Reset state before populating.
        self._users.clear()
        self._username_index.clear()
        self._requests.clear()
        self._notifications.clear()
        self._spontaneous.clear()
        self._transactions.clear()
        self._next_ids.update(data.get("next_ids", {}))
        for u in data.get("users", []):
            user = User.from_dict(u)
            self._users[user.id] = user
            self._username_index[user.username] = user.id
        for r in data.get("requests", []):
            req = FavorRequest.from_dict(r)
            self._requests[req.id] = req
        for n in data.get("notifications", []):
            note = Notification.from_dict(n)
            self._notifications[note.id] = note
        for a in data.get("spontaneous", []):
            act = SpontaneousAct.from_dict(a)
            self._spontaneous[act.id] = act
        for t in data.get("transactions", []):
            tx = Transaction.from_dict(t)
            self._transactions[tx.id] = tx
