"""Reactions service.

Users can react to two event types: spontaneous acts and completed paid
transactions. One reaction per (user, target) — re-reacting with a
different glyph replaces. Re-reacting with the same glyph is a no-op.
Removing happens via ``remove`` which silently no-ops if no reaction is
present.
"""

from __future__ import annotations

from typing import Any, Dict, List

from favorgame.errors import NotRegisteredError, ValidationError
from favorgame.models import REACTION_GLYPHS, Reaction, ReactionTarget
from favorgame.repository import Repository


class ReactionService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def react(
        self,
        *,
        user_id: int,
        target: Any,
        target_id: int,
        glyph: str,
    ) -> Reaction:
        if not self.repo.has_user(user_id):
            raise NotRegisteredError(f"user {user_id} is not registered")
        if glyph not in REACTION_GLYPHS:
            raise ValidationError(
                f"unknown glyph {glyph!r}; allowed: {REACTION_GLYPHS}"
            )
        target = ReactionTarget.parse(target)
        # Verify the underlying event exists.
        self._verify_target(target, target_id)
        rx = Reaction(
            id=self.repo.next_id("reaction"),
            target=target,
            target_id=target_id,
            user_id=user_id,
            glyph=glyph,
        )
        return self.repo.upsert_reaction(rx)

    def remove(self, *, user_id: int, target: Any, target_id: int) -> bool:
        target = ReactionTarget.parse(target)
        return self.repo.remove_reaction(
            user_id=user_id, target=target, target_id=target_id
        )

    def list_for(self, *, target: Any, target_id: int) -> List[Reaction]:
        return self.repo.list_reactions(
            target=ReactionTarget.parse(target), target_id=target_id
        )

    def summary_for(self, *, target: Any, target_id: int) -> Dict[str, int]:
        """Return a glyph→count map for one target. Empty dict for no reactions."""
        out: Dict[str, int] = {}
        for r in self.list_for(target=target, target_id=target_id):
            out[r.glyph] = out.get(r.glyph, 0) + 1
        return out

    def _verify_target(self, target: ReactionTarget, target_id: int) -> None:
        if target is ReactionTarget.SPONTANEOUS:
            if not any(a.id == target_id for a in self.repo.list_spontaneous()):
                raise ValidationError(f"no spontaneous act with id {target_id}")
        elif target is ReactionTarget.TRANSACTION:
            if not any(t.id == target_id for t in self.repo.list_transactions()):
                raise ValidationError(f"no transaction with id {target_id}")
