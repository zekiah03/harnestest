"""Leaderboard helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from favorgame.models import User
from favorgame.repository import Repository


@dataclass(frozen=True)
class RankEntry:
    rank: int
    user: User


class RankingService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def leaderboard(self, limit: Optional[int] = None) -> List[RankEntry]:
        users = sorted(
            self.repo.list_users(),
            key=lambda u: (-u.points, u.username),
        )
        if limit is not None:
            users = users[:limit]
        entries: List[RankEntry] = []
        previous_points: Optional[int] = None
        previous_rank = 0
        for index, user in enumerate(users, start=1):
            if user.points == previous_points:
                rank = previous_rank
            else:
                rank = index
                previous_rank = rank
                previous_points = user.points
            entries.append(RankEntry(rank=rank, user=user))
        return entries

    def rank_of(self, user_id: int) -> Optional[int]:
        for entry in self.leaderboard():
            if entry.user.id == user_id:
                return entry.rank
        return None
