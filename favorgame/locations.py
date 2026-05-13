"""Mock physical locations for proximity-based notification fan-out.

A user picks a current location (a station or neighborhood); when they
post a paid request, the request inherits that location and is only
broadcast to other registered users in the same location — making the
"瞬間的に困ってる" mechanic actually local. ``ANYWHERE`` is an opt-out
that means "either send to me regardless of where the request came from,
or send my request to everyone": it preserves backward compatibility
with calls that don't specify a location.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


ANYWHERE = ""  # the sentinel — no geographic restriction either way


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    region: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Hand-picked station / district set. Adding new entries here is the only
# way to extend the taxonomy — the frontend and API both render from this
# single source.
LOCATIONS: List[Location] = [
    Location("shinjuku",      "新宿駅",        "tokyo"),
    Location("shibuya",       "渋谷駅",        "tokyo"),
    Location("tokyo",         "東京駅",        "tokyo"),
    Location("ikebukuro",     "池袋駅",        "tokyo"),
    Location("shinagawa",     "品川駅",        "tokyo"),
    Location("ueno",          "上野駅",        "tokyo"),
    Location("osaka_umeda",   "大阪・梅田",    "kansai"),
    Location("namba",         "難波",          "kansai"),
    Location("nagoya",        "名古屋駅",      "chubu"),
    Location("kyoto",         "京都駅",        "kansai"),
    Location("sapporo",       "札幌駅",        "hokkaido"),
    Location("fukuoka_tenjin","福岡・天神",    "kyushu"),
]

_BY_KEY: Dict[str, Location] = {loc.key: loc for loc in LOCATIONS}


def is_valid(key: str) -> bool:
    return key == ANYWHERE or key in _BY_KEY


def get(key: str) -> Optional[Location]:
    """Look up a Location by key. Returns None for ANYWHERE or unknown."""
    return _BY_KEY.get(key)


def reaches(request_location: str, recipient_location: str) -> bool:
    """Will a request posted at ``request_location`` notify a user whose
    current location is ``recipient_location``?

    Either side being ``ANYWHERE`` is permissive: a broadcast request goes
    everywhere, and an unanchored recipient receives everything.
    """
    if request_location == ANYWHERE:
        return True
    if recipient_location == ANYWHERE:
        return True
    return request_location == recipient_location
