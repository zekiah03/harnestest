"""Tests for the Repository persistence layer."""

import pytest

from favorgame.errors import DuplicateError, NotFoundError
from favorgame.models import FavorKind, FavorRequest, User
from favorgame.repository import Repository


def test_add_and_get_user(tmp_path):
    repo = Repository(tmp_path / "state.json")
    user = User(id=repo.next_id("user"), username="alice")
    repo.add_user(user)
    assert repo.get_user(user.id).username == "alice"
    assert repo.get_user_by_username("alice").id == user.id


def test_get_unknown_user_raises(tmp_path):
    repo = Repository(tmp_path / "state.json")
    with pytest.raises(NotFoundError):
        repo.get_user(999)
    with pytest.raises(NotFoundError):
        repo.get_user_by_username("ghost")


def test_duplicate_username_rejected(tmp_path):
    repo = Repository(tmp_path / "state.json")
    repo.add_user(User(id=1, username="alice"))
    with pytest.raises(DuplicateError):
        repo.add_user(User(id=2, username="alice"))


def test_next_id_is_monotonic(tmp_path):
    repo = Repository(tmp_path / "state.json")
    a = repo.next_id("user")
    b = repo.next_id("user")
    c = repo.next_id("user")
    assert (a, b, c) == (1, 2, 3)


def test_next_id_unknown_kind(tmp_path):
    repo = Repository(tmp_path / "state.json")
    with pytest.raises(KeyError):
        repo.next_id("nope")


def test_save_and_reload_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    repo = Repository(path)
    repo.add_user(User(id=repo.next_id("user"), username="alice", wallet_yen=500, points=7))
    repo.add_user(User(id=repo.next_id("user"), username="bob"))
    req = FavorRequest(
        id=repo.next_id("request"),
        requester_id=1,
        kind=FavorKind.SEAT,
        bounty_yen=100,
    )
    repo.add_request(req)
    repo.save()

    fresh = Repository(path)
    assert {u.username for u in fresh.list_users()} == {"alice", "bob"}
    assert fresh.get_user_by_username("alice").points == 7
    assert fresh.list_requests()[0].kind is FavorKind.SEAT
    # next_ids preserved
    assert fresh.next_id("user") == 3
    assert fresh.next_id("request") == 2


def test_in_memory_repo(tmp_path):
    repo = Repository(path=None)
    repo.add_user(User(id=1, username="alice"))
    repo.save()  # no-op
    assert repo.get_user(1).username == "alice"


def test_empty_state_file_is_ok(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("")
    repo = Repository(path)
    assert repo.list_users() == []
