"""FavorRequest lifecycle service.

A paid request goes OPEN -> ACCEPTED -> COMPLETED. Yen is debited from the
requester's wallet at request creation (escrow) and credited to the
accepter on completion. On CANCELLED / EXPIRED the escrowed yen is refunded.
"""

from __future__ import annotations

from typing import Any, List, Optional

from favorgame.errors import (
    InsufficientFundsError,
    NotFoundError,
    NotRegisteredError,
    StateError,
    ValidationError,
)
from favorgame.ledger import Ledger
from favorgame.models import (
    FavorKind,
    FavorRequest,
    Notification,
    NotificationResponse,
    RequestStatus,
    utcnow,
)
from favorgame.notifications import NotificationService
from favorgame.points import points_for_bounty, requester_penalty
from favorgame.repository import Repository


# An internal sentinel account id for escrow. Yen leaves the requester's
# wallet immediately when a request opens but doesn't enter the accepter's
# wallet until completion — we track the float on the request itself, no
# extra user record needed. (We do not record an escrow Transaction; the
# transaction is recorded only when escrow is released to its final payee.)


class FavorService:
    def __init__(
        self,
        repo: Repository,
        ledger: Ledger,
        notifications: NotificationService,
    ) -> None:
        self.repo = repo
        self.ledger = ledger
        self.notifications = notifications

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------
    def create_request(
        self,
        *,
        requester_id: int,
        kind: Any,
        bounty_yen: int,
        description: str = "",
    ) -> FavorRequest:
        requester = self.repo.get_user(requester_id)
        if bounty_yen < 0:
            raise ValidationError("bounty_yen must be >= 0")
        if requester.wallet_yen < bounty_yen:
            raise InsufficientFundsError(
                f"user {requester.username!r} cannot escrow {bounty_yen} yen "
                f"with balance {requester.wallet_yen}"
            )
        request = FavorRequest(
            id=self.repo.next_id("request"),
            requester_id=requester_id,
            kind=FavorKind.parse(kind),
            bounty_yen=bounty_yen,
            description=description,
            location=requester.location,
        )
        self.repo.add_request(request)
        # Escrow: yen leaves wallet now.
        requester.wallet_yen -= bounty_yen
        # Notify the rest of the network.
        self.notifications.fan_out(request)
        return request

    # ------------------------------------------------------------------
    # accept
    # ------------------------------------------------------------------
    def accept_request(
        self, *, notification_id: int, accepter_id: int
    ) -> FavorRequest:
        note = self.repo.get_notification(notification_id)
        if note.recipient_id != accepter_id:
            raise NotRegisteredError(
                f"user {accepter_id} cannot accept notification {notification_id} "
                "(not the recipient)"
            )
        request = self.repo.get_request(note.request_id)
        if request.status is not RequestStatus.OPEN:
            raise StateError(
                f"request {request.id} is {request.status.value}, cannot accept"
            )
        if not self.repo.has_user(accepter_id):
            raise NotRegisteredError(f"user {accepter_id} is not registered")
        if accepter_id == request.requester_id:
            raise ValidationError("cannot accept your own request")
        # Mark this notification accepted; auto-ignore the rest.
        note.respond(NotificationResponse.ACCEPTED)
        self.notifications.auto_ignore_pending_for(request.id)
        request.status = RequestStatus.ACCEPTED
        request.accepter_id = accepter_id
        request.accepted_at = utcnow()
        return request

    # ------------------------------------------------------------------
    # complete
    # ------------------------------------------------------------------
    def complete_request(
        self, *, request_id: int, actor_id: int
    ) -> FavorRequest:
        """Mark a request done. Only the requester may complete (confirm).

        Releases escrowed yen to the accepter and credits reputation points.
        """
        request = self.repo.get_request(request_id)
        if request.status is not RequestStatus.ACCEPTED:
            raise StateError(
                f"request {request.id} is {request.status.value}, cannot complete"
            )
        if actor_id != request.requester_id:
            raise ValidationError("only the requester may confirm completion")
        accepter_id = request.accepter_id
        if accepter_id is None:
            raise StateError(f"request {request.id} has no accepter")
        # Release escrowed yen as a transfer from requester -> accepter.
        # The yen has already left the requester's wallet on open(); we
        # restore it temporarily so Ledger.transfer's balance check passes.
        requester = self.repo.get_user(request.requester_id)
        requester.wallet_yen += request.bounty_yen
        bonus_points = points_for_bounty(request.bounty_yen)
        # Yen-only transfer through the ledger — bonus reputation is awarded
        # to the accepter out of the system pool, not deducted from the payer.
        self.ledger.transfer(
            payer_id=request.requester_id,
            payee_id=accepter_id,
            yen_amount=request.bounty_yen,
            point_amount=0,
            memo=f"complete:{request.kind.value}",
            request_id=request.id,
        )
        if bonus_points:
            accepter = self.repo.get_user(accepter_id)
            accepter.points += bonus_points
        # Additional small reputation hit for the requester for paying for help.
        penalty = requester_penalty()
        if penalty:
            requester.points -= penalty
        request.status = RequestStatus.COMPLETED
        request.completed_at = utcnow()
        return request

    # ------------------------------------------------------------------
    # cancel / expire
    # ------------------------------------------------------------------
    def cancel_request(self, *, request_id: int, actor_id: int) -> FavorRequest:
        request = self.repo.get_request(request_id)
        if actor_id != request.requester_id:
            raise ValidationError("only the requester may cancel")
        if request.status not in (RequestStatus.OPEN, RequestStatus.ACCEPTED):
            raise StateError(
                f"cannot cancel a {request.status.value} request"
            )
        # Refund escrow back to the requester.
        self._refund(request)
        if request.status is RequestStatus.OPEN:
            self.notifications.auto_ignore_pending_for(request.id)
        request.status = RequestStatus.CANCELLED
        return request

    def expire_request(self, *, request_id: int) -> FavorRequest:
        request = self.repo.get_request(request_id)
        if request.status is not RequestStatus.OPEN:
            raise StateError(
                f"cannot expire a {request.status.value} request"
            )
        self._refund(request)
        self.notifications.auto_ignore_pending_for(request.id)
        request.status = RequestStatus.EXPIRED
        return request

    def _refund(self, request: FavorRequest) -> None:
        requester = self.repo.get_user(request.requester_id)
        requester.wallet_yen += request.bounty_yen

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def open_requests(self) -> List[FavorRequest]:
        return [r for r in self.repo.list_requests() if r.status is RequestStatus.OPEN]

    def requests_by(self, requester_id: int) -> List[FavorRequest]:
        return [r for r in self.repo.list_requests() if r.requester_id == requester_id]

    def find_notification_for(
        self, *, request_id: int, recipient_id: int
    ) -> Optional[Notification]:
        for n in self.repo.list_notifications(request_id=request_id, recipient_id=recipient_id):
            return n
        return None
