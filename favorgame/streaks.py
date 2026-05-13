"""Daily streak computation.

A user's "streak" is the count of consecutive JST calendar days on which
they were *active* — defined as logging at least one spontaneous act (as
giver) or appearing in a Transaction (paid favor completion, either side).

The function is pure: pass a user + repository snapshot + ``now`` and
get back the streak as of that instant. The UI shows the current streak
and the longest run ever; tests pin ``now`` so they're stable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, Optional, Set

from favorgame.models import User
from favorgame.multipliers import JST
from favorgame.repository import Repository


@dataclass(frozen=True)
class Streak:
    current: int                # consecutive days through today (JST)
    longest: int                # best run ever
    last_active: Optional[str]  # ISO date (JST) of the user's most recent active day

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _active_days_jst(user: User, repo: Repository) -> Set[date]:
    """Return the set of JST calendar dates on which the user was active."""
    days: Set[date] = set()
    for act in repo.list_spontaneous():
        if act.giver_id == user.id:
            days.add(act.created_at.astimezone(JST).date())
    for tx in repo.list_transactions():
        if tx.payer_id == user.id or tx.payee_id == user.id:
            days.add(tx.created_at.astimezone(JST).date())
    return days


def _longest_run(days: Set[date]) -> int:
    if not days:
        return 0
    ordered = sorted(days)
    best = run = 1
    for i in range(1, len(ordered)):
        if ordered[i] - ordered[i - 1] == timedelta(days=1):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def streak_for(
    user: User,
    repo: Repository,
    now: Optional[datetime] = None,
) -> Streak:
    """Compute current + longest streak for ``user`` as of ``now``."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(JST).date()
    days = _active_days_jst(user, repo)

    # The user has until midnight of the *next* day to act and keep the
    # streak alive. So if today has no entry yet, fall back to yesterday
    # before declaring the streak broken.
    walk = today
    if walk not in days:
        walk = walk - timedelta(days=1)

    current = 0
    while walk in days:
        current += 1
        walk = walk - timedelta(days=1)

    last_active = max(days).isoformat() if days else None
    return Streak(current=current, longest=_longest_run(days), last_active=last_active)
