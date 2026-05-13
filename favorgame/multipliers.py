"""Time-of-day / day-of-week multipliers for kindness rewards.

The intent is to layer a "right place, right time" texture over the
otherwise-flat reward table. Giving up your seat during the morning
rush is a much bigger deal than giving it up at 14:00 on a quiet
afternoon; carrying someone's heavy bag at midnight is more notable
than at noon; minding a kid on a Saturday afternoon helps more parents
than minding one Tuesday morning.

All multipliers are *pure functions of the clock* — no per-user
state, no DB rows. The frontend reads ``active_multipliers(now)`` and
renders a strip; the service layer applies ``multiplier_for(kind, now)``
when crediting a spontaneous act.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone, timedelta
from typing import List, Optional, Tuple

from favorgame.models import FavorKind


# Japan Standard Time = UTC+9. We pin to JST so "rush hour" makes sense
# from a Japanese-society viewpoint regardless of where the server runs.
JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Multiplier:
    """An active bonus window."""

    kind: FavorKind
    factor: float
    reason: str        # short Japanese label for the UI ("朝ラッシュ", "週末" など)
    starts_at_hour: int
    ends_at_hour: int  # exclusive (24h clock, JST)
    weekdays_only: bool = False
    weekends_only: bool = False

    def applies_to(self, kind: FavorKind, now: datetime) -> bool:
        if kind is not self.kind:
            return False
        local = now.astimezone(JST)
        weekday = local.weekday()  # 0=Mon, 6=Sun
        if self.weekdays_only and weekday >= 5:
            return False
        if self.weekends_only and weekday < 5:
            return False
        h = local.hour
        if self.starts_at_hour <= self.ends_at_hour:
            return self.starts_at_hour <= h < self.ends_at_hour
        # Wraps midnight (e.g. 23..2).
        return h >= self.starts_at_hour or h < self.ends_at_hour


# Hand-tuned schedule. Tweaking these here updates both backend and UI.
SCHEDULE: List[Multiplier] = [
    Multiplier(
        kind=FavorKind.SEAT, factor=2.0, reason="朝ラッシュ",
        starts_at_hour=7, ends_at_hour=9, weekdays_only=True,
    ),
    Multiplier(
        kind=FavorKind.SEAT, factor=2.0, reason="夕ラッシュ",
        starts_at_hour=17, ends_at_hour=19, weekdays_only=True,
    ),
    Multiplier(
        kind=FavorKind.LUGGAGE, factor=1.5, reason="深夜便",
        starts_at_hour=23, ends_at_hour=2,  # wraps midnight
    ),
    Multiplier(
        kind=FavorKind.CHILD_WATCH, factor=2.0, reason="週末",
        starts_at_hour=0, ends_at_hour=24, weekends_only=True,
    ),
    Multiplier(
        kind=FavorKind.UMBRELLA, factor=1.8, reason="夕立タイム",
        starts_at_hour=15, ends_at_hour=19,
    ),
    Multiplier(
        kind=FavorKind.TRANSLATE, factor=1.5, reason="観光時間",
        starts_at_hour=10, ends_at_hour=18, weekends_only=True,
    ),
]


def multiplier_for(kind: FavorKind, now: Optional[datetime] = None) -> Tuple[float, Optional[Multiplier]]:
    """Return ``(factor, source)``. ``source`` is the winning Multiplier or None.

    If multiple windows match the same kind at the same instant, the highest
    factor wins.
    """
    now = now or datetime.now(timezone.utc)
    candidates = [m for m in SCHEDULE if m.applies_to(kind, now)]
    if not candidates:
        return (1.0, None)
    winner = max(candidates, key=lambda m: m.factor)
    return (winner.factor, winner)


def active_multipliers(now: Optional[datetime] = None) -> List[Multiplier]:
    """Every multiplier currently in force across all kinds.

    Frontend renders this as a strip ("いまは席譲り 2倍 / 深夜便 1.5倍").
    """
    now = now or datetime.now(timezone.utc)
    return [m for m in SCHEDULE if m.applies_to(m.kind, now)]
