"""Achievement engine.

A pure-function evaluator. Given a User and the current Repository
snapshot, it returns a list of ``AchievementStatus`` — one per achievement
in the catalogue — describing how far the user has progressed and whether
the badge has been earned.

State is *not* stored. Every call re-derives counts from the underlying
log of transactions, spontaneous acts, and favor requests. The UI is then
free to diff two snapshots to fire "achievement unlocked!" celebrations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Set

from favorgame.models import FavorKind, RequestStatus, User
from favorgame.repository import Repository


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str
    icon: str           # icon key the frontend resolves to an SVG
    target: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AchievementStatus:
    achievement: Achievement
    progress: int       # current count, clamped to >= 0
    earned: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "achievement": self.achievement.to_dict(),
            "progress": self.progress,
            "earned": self.earned,
            "percent": (
                100 if self.earned
                else min(100, round(100 * self.progress / self.achievement.target))
            ),
        }


# ----------------------------------------------------------------------
# calculators — each returns the user's current "count" for an achievement
# ----------------------------------------------------------------------
def _count_spontaneous_as_giver(repo: Repository, user_id: int, kind: FavorKind = None) -> int:
    n = 0
    for a in repo.list_spontaneous():
        if a.giver_id != user_id:
            continue
        if kind is not None and a.kind is not kind:
            continue
        n += 1
    return n


def _first_kindness(user: User, repo: Repository) -> int:
    return _count_spontaneous_as_giver(repo, user.id)


def _seat_giver_10(user: User, repo: Repository) -> int:
    return _count_spontaneous_as_giver(repo, user.id, FavorKind.SEAT)


def _luggage_pro(user: User, repo: Repository) -> int:
    return _count_spontaneous_as_giver(repo, user.id, FavorKind.LUGGAGE)


def _child_minder(user: User, repo: Repository) -> int:
    return _count_spontaneous_as_giver(repo, user.id, FavorKind.CHILD_WATCH)


def _first_paid(user: User, repo: Repository) -> int:
    return sum(1 for r in repo.list_requests() if r.requester_id == user.id)


def _rescuer_10(user: User, repo: Repository) -> int:
    return sum(
        1
        for r in repo.list_requests()
        if r.accepter_id == user.id and r.status is RequestStatus.COMPLETED
    )


def _benefactor_5000(user: User, repo: Repository) -> int:
    total = 0
    for r in repo.list_requests():
        if r.requester_id == user.id and r.status is RequestStatus.COMPLETED:
            total += r.bounty_yen
    return total


def _three_kinds(user: User, repo: Repository) -> int:
    """Spontaneously did 席 / 荷物 / トイレ at least once each."""
    target_kinds = {FavorKind.SEAT, FavorKind.LUGGAGE, FavorKind.TOILET_ORDER}
    done: Set[FavorKind] = set()
    for a in repo.list_spontaneous():
        if a.giver_id == user.id and a.kind in target_kinds:
            done.add(a.kind)
    return len(done)


def _all_kinds(user: User, repo: Repository) -> int:
    done: Set[FavorKind] = set()
    for a in repo.list_spontaneous():
        if a.giver_id == user.id:
            done.add(a.kind)
    return len(done)


def _tier_regular(user: User, repo: Repository) -> int:
    return max(0, min(50, user.points))


# ----------------------------------------------------------------------
# catalogue
# ----------------------------------------------------------------------
ACHIEVEMENTS: List[Achievement] = [
    Achievement("first_kindness", "はじめての親切", "自発的な親切を1回記録した",  "sprout",    target=1),
    Achievement("seat_giver_10",  "席譲り常習",   "自発的に席を10回譲った",     "seat",      target=10),
    Achievement("luggage_pro",    "荷物持ち達人", "自発的に荷物を5回持った",     "luggage",   target=5),
    Achievement("child_minder",   "子守りプロ",   "自発的に子供を3回見守った",   "child",     target=3),
    Achievement("first_paid",     "はじめての投資","金銭付きお願いを1回出した",  "yen",       target=1),
    Achievement("rescuer_10",     "救助の友",     "金銭付き依頼を10件完了した",  "lifebuoy",  target=10),
    Achievement("benefactor_5k",  "大金主",       "完了依頼で累計5000円支払った","wallet",    target=5000),
    Achievement("three_kinds",    "三方良し",     "席・荷物・トイレを自発で1回ずつ","handshake", target=3),
    Achievement("all_kinds",      "万事屋",       "自発で12種類すべてを経験した", "sparkles",  target=12),
    Achievement("tier_regular",   "常連入り",     "常連ティア (50pt) に到達した", "gem",       target=50),
]


_CALCULATORS: Dict[str, Callable[[User, Repository], int]] = {
    "first_kindness": _first_kindness,
    "seat_giver_10":  _seat_giver_10,
    "luggage_pro":    _luggage_pro,
    "child_minder":   _child_minder,
    "first_paid":     _first_paid,
    "rescuer_10":     _rescuer_10,
    "benefactor_5k":  _benefactor_5000,
    "three_kinds":    _three_kinds,
    "all_kinds":      _all_kinds,
    "tier_regular":   _tier_regular,
}


def evaluate_for(user: User, repo: Repository) -> List[AchievementStatus]:
    """Return one ``AchievementStatus`` per achievement in catalogue order."""
    out: List[AchievementStatus] = []
    for ach in ACHIEVEMENTS:
        calculator = _CALCULATORS[ach.id]
        progress = max(0, calculator(user, repo))
        out.append(
            AchievementStatus(
                achievement=ach,
                progress=progress,
                earned=progress >= ach.target,
            )
        )
    return out


def earned_for(user: User, repo: Repository) -> List[Achievement]:
    """Subset of the catalogue the user has actually earned."""
    return [s.achievement for s in evaluate_for(user, repo) if s.earned]
