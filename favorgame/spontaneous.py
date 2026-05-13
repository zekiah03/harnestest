"""Service for self-reported spontaneous good deeds (no money)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from favorgame.errors import NotRegisteredError, ValidationError
from favorgame.models import FavorKind, SpontaneousAct
from favorgame.multipliers import multiplier_for
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
        now: Optional[datetime] = None,
    ) -> SpontaneousAct:
        if giver_id == receiver_id:
            raise ValidationError("giver and receiver must differ")
        if not self.repo.has_user(giver_id):
            raise NotRegisteredError(f"giver {giver_id} is not registered")
        if not self.repo.has_user(receiver_id):
            raise NotRegisteredError(f"receiver {receiver_id} is not registered")
        kind_enum = FavorKind.parse(kind)
        reward = reward_for_spontaneous(kind_enum)
        factor, source = multiplier_for(kind_enum, now=now)
        # Multiplier inflates only the giver gain. Receiver penalty stays
        # at the base rate — we want to reward generosity in-the-moment
        # without doubly punishing the recipient for being there.
        giver_gain = int(round(reward.giver_delta * factor))
        receiver_loss = reward.receiver_delta
        giver = self.repo.get_user(giver_id)
        receiver = self.repo.get_user(receiver_id)
        giver.points += giver_gain
        receiver.points += receiver_loss
        act = SpontaneousAct(
            id=self.repo.next_id("spontaneous"),
            giver_id=giver_id,
            receiver_id=receiver_id,
            kind=kind_enum,
            note=note,
            giver_delta=giver_gain,
            receiver_delta=receiver_loss,
            multiplier=factor,
            multiplier_reason=source.reason if source else "",
        )
        self.repo.add_spontaneous(act)
        return act
