"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from favorgame.game import Game


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "multipliers: enable the live time-of-day multiplier schedule for this test",
    )


@pytest.fixture(autouse=True)
def _stable_clock(request, monkeypatch):
    """Most tests should be insensitive to the wall clock — they assert on
    base point math, not on the time-of-day bonus. We blank out the
    multiplier schedule by default and let tests that *want* to exercise
    it opt back in with ``@pytest.mark.multipliers``.
    """
    if "multipliers" in request.keywords:
        return
    monkeypatch.setattr("favorgame.multipliers.SCHEDULE", [])


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
