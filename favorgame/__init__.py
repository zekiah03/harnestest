"""FavorGame: a real-world favor-exchange game.

Users earn or lose points for everyday kind acts (giving up a seat, carrying
luggage) and can also post small paid requests ("100 yen to swap toilet
order", "200 yen to give up your seat so I can work") that get pushed as
notifications to nearby registered users.
"""

from favorgame.models import (
    FavorKind,
    FavorRequest,
    Notification,
    NotificationResponse,
    RequestStatus,
    SpontaneousAct,
    Transaction,
    User,
)
from favorgame.repository import Repository

__all__ = [
    "FavorKind",
    "FavorRequest",
    "Notification",
    "NotificationResponse",
    "Repository",
    "RequestStatus",
    "SpontaneousAct",
    "Transaction",
    "User",
]

__version__ = "0.1.0"
