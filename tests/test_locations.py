"""Tests for the location taxonomy and notification filtering."""

import pytest

from favorgame.errors import ValidationError
from favorgame.locations import ANYWHERE, LOCATIONS, get, is_valid, reaches
from favorgame.models import FavorKind


class TestTaxonomy:
    def test_anywhere_is_empty_string(self):
        assert ANYWHERE == ""

    def test_known_keys_are_valid(self):
        assert is_valid("shinjuku")
        assert is_valid("osaka_umeda")

    def test_unknown_key_is_invalid(self):
        assert not is_valid("moon_base")

    def test_anywhere_is_always_valid(self):
        assert is_valid(ANYWHERE)

    def test_get_returns_metadata(self):
        loc = get("shinjuku")
        assert loc is not None
        assert loc.name == "新宿駅"
        assert loc.region == "tokyo"

    def test_get_unknown_is_none(self):
        assert get("nope") is None

    def test_keys_unique(self):
        keys = [l.key for l in LOCATIONS]
        assert len(set(keys)) == len(keys)


class TestReaches:
    def test_same_location_reaches(self):
        assert reaches("shinjuku", "shinjuku")

    def test_different_specific_locations_do_not_reach(self):
        assert not reaches("shinjuku", "shibuya")

    def test_request_anywhere_reaches_everyone(self):
        assert reaches(ANYWHERE, "shinjuku")
        assert reaches(ANYWHERE, "shibuya")
        assert reaches(ANYWHERE, ANYWHERE)

    def test_recipient_anywhere_receives_everything(self):
        assert reaches("shinjuku", ANYWHERE)


class TestRegistrationWithLocation:
    def test_default_registration_has_no_location(self, game):
        u = game.register("alice")
        assert u.location == ""

    def test_explicit_known_location(self, game):
        u = game.register("alice", location="shinjuku")
        assert u.location == "shinjuku"

    def test_unknown_location_rejected(self, game):
        with pytest.raises(ValidationError):
            game.register("alice", location="moon_base")

    def test_set_location_updates_user(self, populated_game):
        populated_game.set_location("alice", "shinjuku")
        assert populated_game.user("alice").location == "shinjuku"


class TestRequestInheritsLocation:
    def test_request_captures_requester_location(self, game):
        game.register("alice", starting_yen=1000, location="shinjuku")
        game.register("bob", starting_yen=1000, location="shibuya")
        req = game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        assert req.location == "shinjuku"


class TestNotificationFanOutFiltering:
    def test_request_only_fans_to_same_location(self, game):
        game.register("alice", starting_yen=1000, location="shinjuku")
        game.register("bob",   starting_yen=1000, location="shinjuku")
        game.register("carol", starting_yen=1000, location="shibuya")
        req = game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        recipients = {n.recipient_id for n in game.repo.list_notifications(request_id=req.id)}
        bob_id = game.user("bob").id
        carol_id = game.user("carol").id
        assert bob_id in recipients
        assert carol_id not in recipients

    def test_anywhere_recipient_receives_specific_request(self, game):
        # Carol is at "anywhere" — she should still get Alice's local request.
        game.register("alice", starting_yen=1000, location="shinjuku")
        game.register("carol", starting_yen=1000, location=ANYWHERE)
        req = game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        recipients = {n.recipient_id for n in game.repo.list_notifications(request_id=req.id)}
        assert game.user("carol").id in recipients

    def test_anywhere_request_fans_to_everyone(self, game):
        # Alice didn't anchor her location — fans to all locations.
        game.register("alice", starting_yen=1000)  # ANYWHERE
        game.register("bob",   starting_yen=1000, location="shibuya")
        game.register("carol", starting_yen=1000, location="shinjuku")
        req = game.request_favor(
            requester="alice", kind=FavorKind.SEAT, bounty_yen=100,
        )
        recipients = {n.recipient_id for n in game.repo.list_notifications(request_id=req.id)}
        assert game.user("bob").id in recipients
        assert game.user("carol").id in recipients
