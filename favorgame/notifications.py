"""Notification fan-out service.

When a FavorRequest is opened we fan out one Notification per *other*
registered user. Each recipient can then independently ignore or accept the
request. The first ACCEPT wins; subsequent ones are auto-ignored when the
request moves out of OPEN.
"""

from __future__ import annotations

from typing import List

from favorgame.errors import StateError
from favorgame.models import (
    FavorRequest,
    Notification,
    NotificationResponse,
    RequestStatus,
)
from favorgame.repository import Repository


class NotificationService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def fan_out(self, request: FavorRequest) -> List[Notification]:
        """Create one Notification per registered user except the requester."""
        if request.status is not RequestStatus.OPEN:
            raise StateError(
                f"can only fan out OPEN requests; got {request.status.value}"
            )
        notifications: List[Notification] = []
        for user in self.repo.list_users():
            if user.id == request.requester_id:
                continue
            note = Notification(
                id=self.repo.next_id("notification"),
                request_id=request.id,
                recipient_id=user.id,
            )
            self.repo.add_notification(note)
            notifications.append(note)
        return notifications

    def ignore(self, notification_id: int) -> Notification:
        note = self.repo.get_notification(notification_id)
        note.respond(NotificationResponse.IGNORED)
        return note

    def accept(self, notification_id: int) -> Notification:
        note = self.repo.get_notification(notification_id)
        note.respond(NotificationResponse.ACCEPTED)
        return note

    def auto_ignore_pending_for(self, request_id: int) -> int:
        """Mark all pending notifications for a request as IGNORED. Returns count."""
        n = 0
        for note in self.repo.list_notifications(request_id=request_id):
            if note.response is NotificationResponse.PENDING:
                note.respond(NotificationResponse.IGNORED)
                n += 1
        return n

    def pending_for(self, recipient_id: int) -> List[Notification]:
        return [
            n
            for n in self.repo.list_notifications(recipient_id=recipient_id)
            if n.response is NotificationResponse.PENDING
        ]
