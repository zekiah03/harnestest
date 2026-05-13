"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from favorgame.game import Game


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "state.json"


@pytest.fixture
def game(state_path: Path) -> Iterator[Game]:
    g = Game(path=state_path)
    yield g
    g.save()


@pytest.fixture
def populated_game(game: Game) -> Game:
    """A Game with three users seeded with 1000 yen each."""
    game.register("alice", display_name="Alice", starting_yen=1000)
    game.register("bob", display_name="Bob", starting_yen=1000)
    game.register("carol", display_name="Carol", starting_yen=1000)
    return game
