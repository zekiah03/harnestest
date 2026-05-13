"""Reputation tiers.

A user's points place them in one of six bands. Tiers are pure data — they
derive from the points value alone, no stored state. The status helper also
returns the *next* tier and a 0..1 progress fraction so a UI can render a
ring or progress bar without doing its own math.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Tier:
    rank: int           # 0 (lowest) .. 5 (highest)
    key: str            # stable machine id
    name: str           # display label (Japanese)
    threshold: int      # entry threshold (inclusive lower bound), in points
    color: str          # hex, hint for the UI ring colour
    icon: str           # icon key the frontend resolves to an SVG

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Ordered ascending by threshold. The 借りあり (in-debt) tier has a very
# negative sentinel threshold so the "largest threshold <= points" lookup
# always succeeds, even for unrealistic negative points.
TIERS: List[Tier] = [
    Tier(rank=0, key="debt",       name="借りあり", threshold=-10_000, color="#ff6b8a", icon="cloud"),
    Tier(rank=1, key="newbie",     name="新人",       threshold=0,      color="#9aa0b4", icon="sprout"),
    Tier(rank=2, key="apprentice", name="見習い",    threshold=10,     color="#2ee59d", icon="leaf"),
    Tier(rank=3, key="regular",    name="常連",      threshold=50,     color="#4cd0e8", icon="gem"),
    Tier(rank=4, key="master",     name="達人",      threshold=200,    color="#b076ff", icon="star"),
    Tier(rank=5, key="sage",       name="仙人",      threshold=1000,   color="#ffd768", icon="crown"),
]


# Soft visual floor used only for "progress towards 新人" when the user is
# in 借りあり. Real points can be far lower than this; the bar just clamps.
_DEBT_SOFT_FLOOR = -50


def tier_for(points: int) -> Tier:
    """Return the tier whose entry threshold ``points`` has crossed."""
    chosen = TIERS[0]
    for t in TIERS:
        if points >= t.threshold:
            chosen = t
    return chosen


def next_tier(current: Tier) -> Optional[Tier]:
    """Return the tier directly above ``current``, or None if already top."""
    for t in TIERS:
        if t.rank == current.rank + 1:
            return t
    return None


@dataclass(frozen=True)
class TierStatus:
    tier: Tier
    next: Optional[Tier]
    points: int
    points_to_next: Optional[int]    # None when at MAX
    progress: float                  # 0.0 .. 1.0 within the current band

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.to_dict(),
            "next": self.next.to_dict() if self.next else None,
            "points": self.points,
            "points_to_next": self.points_to_next,
            "progress": round(self.progress, 4),
        }


def status_for(points: int) -> TierStatus:
    """Compute the full TierStatus (tier, next, progress) for ``points``."""
    current = tier_for(points)
    upper = next_tier(current)
    if upper is None:
        # At MAX — no progress to compute.
        return TierStatus(
            tier=current,
            next=None,
            points=points,
            points_to_next=None,
            progress=1.0,
        )
    if current.key == "debt":
        # The 借りあり band has a sentinel threshold; use a soft floor so
        # the progress bar gives meaningful feedback as the user crawls
        # back to zero.
        lower = _DEBT_SOFT_FLOOR
    else:
        lower = current.threshold
    span = max(1, upper.threshold - lower)
    raw = (points - lower) / span
    progress = max(0.0, min(1.0, raw))
    return TierStatus(
        tier=current,
        next=upper,
        points=points,
        points_to_next=upper.threshold - points,
        progress=progress,
    )
