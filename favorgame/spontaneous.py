"""Service for self-reported spontaneous good deeds (no money)."""

from __future__ import annotations

from typing import Any

from favorgame.errors import NotRegisteredError, ValidationError
from favorgame.models import FavorKind, SpontaneousAct
from favorgame.points import reward_for_spontaneous
from favorgame.repository import Repository


class SpontaneousService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def log(
        self,
        *,
        giver_id: int,
        receiver_id: int,
        kind: Any,
        note: str = "",
    ) -> SpontaneousAct:
        if giver_id == receiver_id:
            raise ValidationError("giver and receiver must differ")
        if not self.repo.has_user(giver_id):
            raise NotRegisteredError(f"giver {giver_id} is not registered")
        if not self.repo.has_user(receiver_id):
            raise NotRegisteredError(f"receiver {receiver_id} is not registered")
        kind_enum = FavorKind.parse(kind)
        reward = reward_for_spontaneous(kind_enum)
        giver = self.repo.get_user(giver_id)
        receiver = self.repo.get_user(receiver_id)
        giver.points += reward.giver_delta
        receiver.points += reward.receiver_delta
        act = SpontaneousAct(
            id=self.repo.next_id("spontaneous"),
            giver_id=giver_id,
            receiver_id=receiver_id,
            kind=kind_enum,
            note=note,
            giver_delta=reward.giver_delta,
            receiver_delta=reward.receiver_delta,
        )
        self.repo.add_spontaneous(act)
        return act
