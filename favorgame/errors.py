"""Domain errors raised by FavorGame services."""


class FavorGameError(Exception):
    """Base class for all FavorGame errors."""


class NotFoundError(FavorGameError):
    """Raised when an entity is not found by id."""


class DuplicateError(FavorGameError):
    """Raised when a uniqueness constraint is violated."""


class ValidationError(FavorGameError):
    """Raised when input data is malformed or out of range."""


class StateError(FavorGameError):
    """Raised when an operation is illegal in the current entity state."""


class InsufficientFundsError(FavorGameError):
    """Raised when a wallet has too few yen to cover a bounty."""


class NotRegisteredError(FavorGameError):
    """Raised when an actor is not part of the registered network."""
