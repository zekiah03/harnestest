"""End-to-end tests for the Flask API exposed at ``api/index.py``.

Each test gets its own ``FAVORGAME_STATE`` JSON path via ``tmp_path`` so the
network starts empty and tests don't leak state into each other.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

flask = pytest.importorskip("flask")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """Yield a Flask test client backed by a fresh per-test state file."""
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("FAVORGAME_STATE", str(state_file))
    # Force a fresh import each test so STATE_PATH is rebound from the env var.
    sys.modules.pop("api.index", None)
    sys.modules.pop("api", None)
    module = importlib.import_module("api.index")
    yield module.app.test_client()


def _json(resp):
    return json.loads(resp.get_data(as_text=True))


# ----------------------------------------------------------------------
# root + introspection
# ----------------------------------------------------------------------
class TestRoot:
    def test_root_lists_endpoints_and_taxonomies(self, client):
        resp = client.get("/api")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["name"] == "favorgame"
        assert "endpoints" in data
        assert "seat" in data["kinds"]
        assert "open" in data["statuses"]


# ----------------------------------------------------------------------
# users
# ----------------------------------------------------------------------
class TestUsers:
    def test_register_returns_201_and_persists(self, client):
        resp = client.post(
            "/api/users",
            json={"username": "alice", "display_name": "アリス", "starting_yen": 1000},
        )
        assert resp.status_code == 201
        body = _json(resp)
        assert body["username"] == "alice"
        assert body["wallet_yen"] == 1000

        listing = _json(client.get("/api/users"))
        assert any(u["username"] == "alice" for u in listing)

    def test_register_requires_username(self, client):
        resp = client.post("/api/users", json={"display_name": "x"})
        assert resp.status_code == 400
        assert "username" in _json(resp)["error"]

    def test_register_duplicate_fails(self, client):
        client.post("/api/users", json={"username": "alice"})
        resp = client.post("/api/users", json={"username": "alice"})
        assert resp.status_code == 400

    def test_topup_increases_balance(self, client):
        client.post("/api/users", json={"username": "alice"})
        resp = client.post(
            "/api/topup", json={"username": "alice", "yen": 500},
        )
        assert resp.status_code == 200
        assert _json(resp)["wallet_yen"] == 500

    def test_topup_missing_fields(self, client):
        client.post("/api/users", json={"username": "alice"})
        resp = client.post("/api/topup", json={"username": "alice"})
        assert resp.status_code == 400


# ----------------------------------------------------------------------
# favor lifecycle
# ----------------------------------------------------------------------
class TestFavorLifecycle:
    @pytest.fixture
    def trio(self, client):
        for name in ("alice", "bob", "carol"):
            client.post(
                "/api/users",
                json={"username": name, "starting_yen": 1000},
            )
        return client

    def test_full_paid_flow(self, trio):
        resp = trio.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 100},
        )
        assert resp.status_code == 201
        rid = _json(resp)["id"]

        resp = trio.post(
            f"/api/requests/{rid}/accept",
            json={"accepter": "bob"},
        )
        assert resp.status_code == 200
        assert _json(resp)["status"] == "accepted"

        resp = trio.post(
            f"/api/requests/{rid}/complete",
            json={"requester": "alice"},
        )
        assert resp.status_code == 200
        assert _json(resp)["status"] == "completed"

        alice = _json(trio.get("/api/users"))
        bob_user = next(u for u in alice if u["username"] == "bob")
        assert bob_user["wallet_yen"] == 1100
        assert bob_user["points"] == 10

    def test_cancel_refunds(self, trio):
        rid = _json(trio.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 200},
        ))["id"]
        trio.post(f"/api/requests/{rid}/cancel", json={"requester": "alice"})
        users = _json(trio.get("/api/users"))
        alice = next(u for u in users if u["username"] == "alice")
        assert alice["wallet_yen"] == 1000

    def test_accept_requires_accepter_field(self, trio):
        rid = _json(trio.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 100},
        ))["id"]
        resp = trio.post(f"/api/requests/{rid}/accept", json={})
        assert resp.status_code == 400

    def test_create_request_requires_fields(self, trio):
        resp = trio.post("/api/requests", json={"requester": "alice", "kind": "seat"})
        assert resp.status_code == 400

    def test_request_kind_validation_propagates(self, trio):
        resp = trio.post(
            "/api/requests",
            json={"requester": "alice", "kind": "moon", "bounty_yen": 100},
        )
        assert resp.status_code == 400

    def test_list_requests_filter_by_status(self, trio):
        trio.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 100},
        )
        body = _json(trio.get("/api/requests?status=open"))
        assert len(body) == 1
        body = _json(trio.get("/api/requests?status=completed"))
        assert body == []


# ----------------------------------------------------------------------
# spontaneous
# ----------------------------------------------------------------------
class TestSpontaneous:
    def test_spontaneous_records_act(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n})
        resp = client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob", "kind": "seat"},
        )
        assert resp.status_code == 201
        body = _json(resp)
        assert body["giver_delta"] == 5
        assert body["receiver_delta"] == -2

    def test_spontaneous_missing_field(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n})
        resp = client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob"},
        )
        assert resp.status_code == 400


# ----------------------------------------------------------------------
# notifications
# ----------------------------------------------------------------------
class TestNotifications:
    def test_inbox_then_ignore(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n, "starting_yen": 500})
        client.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 100},
        )
        notes = _json(client.get("/api/inbox/bob"))
        assert len(notes) == 1
        nid = notes[0]["id"]
        resp = client.post(
            f"/api/notifications/{nid}/ignore",
            json={"username": "bob"},
        )
        assert resp.status_code == 200
        assert _json(resp)["response"] == "ignored"
        # And the inbox is now empty.
        assert _json(client.get("/api/inbox/bob")) == []

    def test_ignore_belongs_to_other_user_rejected(self, client):
        for n in ("alice", "bob", "carol"):
            client.post("/api/users", json={"username": n, "starting_yen": 500})
        client.post(
            "/api/requests",
            json={"requester": "alice", "kind": "seat", "bounty_yen": 100},
        )
        notes = _json(client.get("/api/inbox/bob"))
        nid = notes[0]["id"]
        # Carol cannot ignore Bob's notification.
        resp = client.post(
            f"/api/notifications/{nid}/ignore",
            json={"username": "carol"},
        )
        assert resp.status_code == 403


# ----------------------------------------------------------------------
# leaderboard + activity
# ----------------------------------------------------------------------
class TestLeaderboardAndActivity:
    def test_leaderboard_orders_by_points(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n})
        client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob", "kind": "luggage"},
        )
        board = _json(client.get("/api/leaderboard"))
        assert board[0]["username"] == "alice"
        assert board[0]["points"] == 8
        assert board[-1]["username"] == "bob"
        assert board[-1]["points"] == -3

    def test_activity_includes_spontaneous(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n})
        client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob", "kind": "seat"},
        )
        events = _json(client.get("/api/activity"))
        assert any(e["kind"] == "spontaneous" for e in events)

    def test_activity_limit(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n})
        for _ in range(3):
            client.post(
                "/api/spontaneous",
                json={"giver": "alice", "receiver": "bob", "kind": "seat"},
            )
        events = _json(client.get("/api/activity?limit=2"))
        assert len(events) == 2


# ----------------------------------------------------------------------
# tier + achievements + profile
# ----------------------------------------------------------------------
class TestTierAndAchievements:
    def test_tier_for_new_user_is_newbie(self, client):
        client.post("/api/users", json={"username": "alice"})
        tier = _json(client.get("/api/tier/alice"))
        assert tier["tier"]["key"] == "newbie"
        assert tier["tier"]["icon"] == "sprout"   # icon is a key, not an emoji
        assert tier["points"] == 0
        assert tier["next"]["key"] == "apprentice"

    def test_achievements_initially_unearned(self, client):
        client.post("/api/users", json={"username": "alice"})
        achs = _json(client.get("/api/achievements/alice"))
        assert achs
        assert all(not a["earned"] for a in achs)
        # No emoji icons leaked.
        for a in achs:
            assert all(ord(c) < 128 for c in a["achievement"]["icon"])

    def test_profile_returns_user_tier_and_achievements(self, client):
        client.post("/api/users", json={"username": "alice", "starting_yen": 100})
        client.post("/api/users", json={"username": "bob"})
        client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob", "kind": "seat"},
        )
        prof = _json(client.get("/api/profile/alice"))
        assert prof["user"]["username"] == "alice"
        assert prof["tier"]["tier"]["key"] == "newbie"
        assert prof["achievements"]["earned_count"] >= 1
        earned_ids = [a["achievement"]["id"] for a in prof["achievements"]["earned"]]
        assert "first_kindness" in earned_ids


# ----------------------------------------------------------------------
# seed
# ----------------------------------------------------------------------
class TestSeed:
    def test_seed_populates_personas(self, client):
        resp = client.post("/api/seed")
        assert resp.status_code == 201
        names = [u["display_name"] for u in _json(resp)["users"]]
        assert "山田アリス" in names

        users = _json(client.get("/api/users"))
        assert len(users) == 5

    def test_seed_refuses_overwrite_without_force(self, client):
        client.post("/api/seed")
        resp = client.post("/api/seed")
        assert resp.status_code == 409

    def test_seed_force_overwrites(self, client):
        client.post("/api/seed")
        resp = client.post("/api/seed?force=true")
        assert resp.status_code == 201
        users = _json(client.get("/api/users"))
        assert len(users) == 5


# ----------------------------------------------------------------------
# quests, streak, multipliers, locations
# ----------------------------------------------------------------------
class TestQuestsApi:
    def test_quests_returns_three_items(self, client):
        client.post("/api/users", json={"username": "alice"})
        quests = _json(client.get("/api/quests/alice"))
        assert len(quests) == 3
        ids = {q["quest"]["id"] for q in quests}
        assert ids == {"variety_3", "helped_2", "closed_1"}
        # All initially incomplete.
        assert all(not q["completed"] for q in quests)


class TestStreakApi:
    def test_initial_streak_is_zero(self, client):
        client.post("/api/users", json={"username": "alice"})
        streak = _json(client.get("/api/streak/alice"))
        assert streak["current"] == 0
        assert streak["longest"] == 0
        assert streak["last_active"] is None


class TestMultipliersApi:
    def test_returns_list(self, client):
        # Default test fixture disables SCHEDULE, so this should be empty.
        data = _json(client.get("/api/multipliers"))
        assert isinstance(data, list)


class TestLocationsApi:
    def test_locations_returns_taxonomy(self, client):
        locs = _json(client.get("/api/locations"))
        keys = {l["key"] for l in locs}
        assert "shinjuku" in keys
        assert "shibuya" in keys

    def test_update_location_endpoint(self, client):
        client.post("/api/users", json={"username": "alice"})
        resp = client.post(
            "/api/users/alice/location", json={"location": "shinjuku"}
        )
        assert resp.status_code == 200
        assert _json(resp)["location"] == "shinjuku"

    def test_update_unknown_location_rejected(self, client):
        client.post("/api/users", json={"username": "alice"})
        resp = client.post(
            "/api/users/alice/location", json={"location": "moon"}
        )
        assert resp.status_code == 400


# ----------------------------------------------------------------------
# reactions
# ----------------------------------------------------------------------
class TestReactionsApi:
    @pytest.fixture
    def with_event(self, client):
        for n in ("alice", "bob"):
            client.post("/api/users", json={"username": n, "starting_yen": 500})
        client.post(
            "/api/spontaneous",
            json={"giver": "alice", "receiver": "bob", "kind": "seat"},
        )
        return client

    def test_add_reaction(self, with_event):
        resp = with_event.post(
            "/api/reactions",
            json={"user": "alice", "target": "spontaneous", "target_id": 1, "glyph": "heart"},
        )
        assert resp.status_code == 201
        assert _json(resp)["glyph"] == "heart"

    def test_unknown_glyph_rejected(self, with_event):
        resp = with_event.post(
            "/api/reactions",
            json={"user": "alice", "target": "spontaneous", "target_id": 1, "glyph": "laser"},
        )
        assert resp.status_code == 400

    def test_reactions_show_in_activity(self, with_event):
        with_event.post(
            "/api/reactions",
            json={"user": "bob", "target": "spontaneous", "target_id": 1, "glyph": "clap"},
        )
        events = _json(with_event.get("/api/activity"))
        spontaneous_events = [e for e in events if e["kind"] == "spontaneous"]
        assert spontaneous_events
        assert spontaneous_events[0]["reactions"] == {"clap": 1}

    def test_remove_reaction(self, with_event):
        with_event.post(
            "/api/reactions",
            json={"user": "alice", "target": "spontaneous", "target_id": 1, "glyph": "heart"},
        )
        resp = with_event.delete(
            "/api/reactions",
            json={"user": "alice", "target": "spontaneous", "target_id": 1},
        )
        assert resp.status_code == 200
        assert _json(resp)["removed"] is True


class TestProfileExpansion:
    def test_profile_includes_quests_and_streak(self, client):
        client.post("/api/users", json={"username": "alice", "location": "shinjuku"})
        prof = _json(client.get("/api/profile/alice"))
        assert "quests" in prof
        assert len(prof["quests"]) == 3
        assert "streak" in prof
        assert "current" in prof["streak"]
        assert prof["location"]["key"] == "shinjuku"


# ----------------------------------------------------------------------
# error surface
# ----------------------------------------------------------------------
class TestErrorSurface:
    def test_unknown_user_returns_400(self, client):
        resp = client.get("/api/tier/ghost")
        assert resp.status_code == 400
        assert "ghost" in _json(resp)["error"]

    def test_404_for_unknown_route(self, client):
        resp = client.get("/api/bogus")
        assert resp.status_code == 404


# ----------------------------------------------------------------------
# emoji audit — guarantees no emoji slips into any API payload
# ----------------------------------------------------------------------
class TestNoEmojiInPayloads:
    def test_no_emoji_in_tier_or_achievement_responses(self, client):
        client.post("/api/seed")
        # Pull every endpoint that surfaces icons and check raw bytes.
        endpoints = [
            "/api/tier/alice",
            "/api/achievements/alice",
            "/api/profile/alice",
            "/api/leaderboard",
        ]
        for path in endpoints:
            resp = client.get(path)
            assert resp.status_code == 200, path
            text = resp.get_data(as_text=True)
            # Codepoint U+1F300 and up covers symbols & pictographs. Any
            # character past plane 0 is suspicious for a label-only API.
            offenders = [c for c in text if ord(c) >= 0x1F000]
            assert not offenders, f"{path} contained {offenders!r}"
