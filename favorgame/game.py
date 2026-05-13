"""Facade that wires the repository and services together.

CLI and tests typically instantiate ``Game`` once and call its high-level
methods rather than reaching into each service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from favorgame.errors import DuplicateError
from favorgame.favors import FavorService
from favorgame.ledger import Ledger
from favorgame.models import FavorRequest, Notification, SpontaneousAct, User
from favorgame.notifications import NotificationService
from favorgame.ranking import RankEntry, RankingService
from favorgame.repository import Repository
from favorgame.spontaneous import SpontaneousService


class Game:
    """High-level entry point for the FavorGame system."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.repo = Repository(path)
        self.ledger = Ledger(self.repo)
        self.notifications = NotificationService(self.repo)
        self.favors = FavorService(self.repo, self.ledger, self.notifications)
        self.spontaneous = SpontaneousService(self.repo)
        self.ranking = RankingService(self.repo)

    # ------------------------------------------------------------------
    # user management
    # ------------------------------------------------------------------
    def register(
        self,
        username: str,
        *,
        display_name: str = "",
        starting_yen: int = 0,
    ) -> User:
        try:
            existing = self.repo.get_user_by_username(username)
        except Exception:
            existing = None
        if existing is not None:
            raise DuplicateError(f"username {username!r} already taken")
        user = User(
            id=self.repo.next_id("user"),
            username=username,
            display_name=display_name,
            wallet_yen=starting_yen,
        )
        self.repo.add_user(user)
        return user

    def user(self, username: str) -> User:
        return self.repo.get_user_by_username(username)

    # ------------------------------------------------------------------
    # paid favors
    # ------------------------------------------------------------------
    def request_favor(
        self,
        *,
        requester: str,
        kind: Any,
        bounty_yen: int,
        description: str = "",
    ) -> FavorRequest:
        user = self.repo.get_user_by_username(requester)
        return self.favors.create_request(
            requester_id=user.id,
            kind=kind,
            bounty_yen=bounty_yen,
            description=description,
        )

    def accept_favor(self, *, accepter: str, request_id: int) -> FavorRequest:
        acc = self.repo.get_user_by_username(accepter)
        note = self.favors.find_notification_for(request_id=request_id, recipient_id=acc.id)
        if note is None:
            from favorgame.errors import NotFoundError

            raise NotFoundError(
                f"no notification for user {accepter!r} on request {request_id}"
            )
        return self.favors.accept_request(
            notification_id=note.id, accepter_id=acc.id
        )

    def complete_favor(self, *, requester: str, request_id: int) -> FavorRequest:
        user = self.repo.get_user_by_username(requester)
        return self.favors.complete_request(request_id=request_id, actor_id=user.id)

    def cancel_favor(self, *, requester: str, request_id: int) -> FavorRequest:
        user = self.repo.get_user_by_username(requester)
        return self.favors.cancel_request(request_id=request_id, actor_id=user.id)

    # ------------------------------------------------------------------
    # spontaneous
    # ------------------------------------------------------------------
    def report_spontaneous(
        self, *, giver: str, receiver: str, kind: Any, note: str = ""
    ) -> SpontaneousAct:
        g = self.repo.get_user_by_username(giver)
        r = self.repo.get_user_by_username(receiver)
        return self.spontaneous.log(
            giver_id=g.id, receiver_id=r.id, kind=kind, note=note
        )

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    def inbox(self, username: str) -> List[Notification]:
        user = self.repo.get_user_by_username(username)
        return self.notifications.pending_for(user.id)

    # ------------------------------------------------------------------
    # ranking
    # ------------------------------------------------------------------
    def leaderboard(self, limit: Optional[int] = None) -> List[RankEntry]:
        return self.ranking.leaderboard(limit=limit)

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------
    def save(self) -> None:
        self.repo.save()
