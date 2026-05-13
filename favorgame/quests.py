"""Daily quests.

A fixed roster of three short challenges that reset every JST midnight:

  1. variety_3   — log 3 *distinct* favor kinds today (any role)
  2. helped_2    — help 2 distinct people today (as giver of a
                   spontaneous act, or as accepter of a completed paid
                   favor)
  3. closed_1    — close out 1 paid favor request today (as either
                   requester confirming, or accepter being credited)

Each call to ``evaluate_for(user, repo, now)`` re-derives progress
from the underlying log — no per-quest persistence is needed. The
bonus mechanic (small point award on first completion of a quest in
a given day) is intentionally NOT implemented here yet: completion
is its own reward in the UI, and adding bonus pts would mean tracking
"already claimed" state per day per user.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Set

from favorgame.models import FavorKind, RequestStatus, User
from favorgame.multipliers import JST
from favorgame.repository import Repository


@dataclass(frozen=True)
class Quest:
    id: str
    name: str
    description: str
    icon: str       # frontend SVG key
    target: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuestStatus:
    quest: Quest
    progress: int
    completed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quest": self.quest.to_dict(),
            "progress": self.progress,
            "completed": self.completed,
            "percent": 100 if self.completed
                       else min(100, round(100 * self.progress / self.quest.target)),
        }


QUESTS: List[Quest] = [
    Quest("variety_3", "今日は3種類", "違う種類の親切を3つ", "sparkles", target=3),
    Quest("helped_2",  "今日は2人助ける", "違う相手を2人助ける", "handshake", target=2),
    Quest("closed_1",  "今日は1依頼を完遂", "金銭付き依頼を1件完了する", "check", target=1),
]


def _today_jst(now: Optional[datetime] = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(JST).date()


def _is_today(ts: datetime, today: date) -> bool:
    return ts.astimezone(JST).date() == today


def _variety_progress(user: User, repo: Repository, today: date) -> int:
    """Count distinct FavorKinds the user has touched today, in any role."""
    seen: Set[FavorKind] = set()
    for act in repo.list_spontaneous():
        if not _is_today(act.created_at, today):
            continue
        if act.giver_id == user.id or act.receiver_id == user.id:
            seen.add(act.kind)
    for req in repo.list_requests():
        if not _is_today(req.created_at, today):
            continue
        # Count if the user is either the requester or an actual accepter.
        if req.requester_id == user.id or req.accepter_id == user.id:
            seen.add(req.kind)
    return len(seen)


def _helped_progress(user: User, repo: Repository, today: date) -> int:
    """Count distinct people the user helped today.

    Counts as helping: being the giver of a spontaneous act today, OR
    being the accepter of a paid request completed today.
    """
    helped: Set[int] = set()
    for act in repo.list_spontaneous():
        if not _is_today(act.created_at, today):
            continue
        if act.giver_id == user.id:
            helped.add(act.receiver_id)
    for req in repo.list_requests():
        if req.status is not RequestStatus.COMPLETED:
            continue
        if req.completed_at is None or not _is_today(req.completed_at, today):
            continue
        if req.accepter_id == user.id:
            helped.add(req.requester_id)
    return len(helped)


def _closed_progress(user: User, repo: Repository, today: date) -> int:
    """Count paid requests completed today that the user was party to."""
    n = 0
    for req in repo.list_requests():
        if req.status is not RequestStatus.COMPLETED:
            continue
        if req.completed_at is None or not _is_today(req.completed_at, today):
            continue
        if req.requester_id == user.id or req.accepter_id == user.id:
            n += 1
    return n


_EVALUATORS = {
    "variety_3": _variety_progress,
    "helped_2":  _helped_progress,
    "closed_1":  _closed_progress,
}


def evaluate_for(
    user: User,
    repo: Repository,
    now: Optional[datetime] = None,
) -> List[QuestStatus]:
    today = _today_jst(now)
    out: List[QuestStatus] = []
    for quest in QUESTS:
        progress = _EVALUATORS[quest.id](user, repo, today)
        out.append(QuestStatus(
            quest=quest,
            progress=progress,
            completed=progress >= quest.target,
        ))
    return out
