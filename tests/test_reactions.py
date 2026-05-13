"""Tests for the reaction service."""

import pytest

from favorgame.errors import NotRegisteredError, ValidationError
from favorgame.models import FavorKind, REACTION_GLYPHS, ReactionTarget


@pytest.fixture
def with_spontaneous(populated_game):
    """A populated game plus one spontaneous act + one completed paid txn."""
    act = populated_game.report_spontaneous(
        giver="alice", receiver="bob", kind=FavorKind.SEAT
    )
    req = populated_game.request_favor(
        requester="carol", kind=FavorKind.TOILET_ORDER, bounty_yen=100,
    )
    populated_game.accept_favor(accepter="bob", request_id=req.id)
    populated_game.complete_favor(requester="carol", request_id=req.id)
    tx = populated_game.repo.list_transactions()[0]
    return populated_game, act, tx


class TestReact:
    def test_can_react_with_each_allowed_glyph(self, with_spontaneous):
        game, act, _ = with_spontaneous
        carol = game.user("carol")
        for glyph in REACTION_GLYPHS:
            rx = game.reactions.react(
                user_id=carol.id, target=ReactionTarget.SPONTANEOUS,
                target_id=act.id, glyph=glyph,
            )
            assert rx.glyph == glyph

    def test_unknown_glyph_rejected(self, with_spontaneous):
        game, act, _ = with_spontaneous
        with pytest.raises(ValidationError):
            game.reactions.react(
                user_id=game.user("carol").id,
                target=ReactionTarget.SPONTANEOUS,
                target_id=act.id,
                glyph="laser",
            )

    def test_unregistered_user_rejected(self, with_spontaneous):
        game, act, _ = with_spontaneous
        with pytest.raises(NotRegisteredError):
            game.reactions.react(
                user_id=9999, target=ReactionTarget.SPONTANEOUS,
                target_id=act.id, glyph="heart",
            )

    def test_missing_target_rejected(self, with_spontaneous):
        game, _, _ = with_spontaneous
        carol = game.user("carol")
        with pytest.raises(ValidationError):
            game.reactions.react(
                user_id=carol.id, target=ReactionTarget.SPONTANEOUS,
                target_id=99999, glyph="heart",
            )

    def test_same_user_replaces_existing_glyph(self, with_spontaneous):
        game, act, _ = with_spontaneous
        carol = game.user("carol")
        game.reactions.react(user_id=carol.id, target="spontaneous",
                             target_id=act.id, glyph="heart")
        game.reactions.react(user_id=carol.id, target="spontaneous",
                             target_id=act.id, glyph="thumb")
        rxs = game.reactions.list_for(target="spontaneous", target_id=act.id)
        assert len(rxs) == 1
        assert rxs[0].glyph == "thumb"

    def test_different_users_each_get_a_reaction(self, with_spontaneous):
        game, act, _ = with_spontaneous
        for who in ("alice", "carol"):
            game.reactions.react(user_id=game.user(who).id,
                                 target="spontaneous", target_id=act.id,
                                 glyph="heart")
        rxs = game.reactions.list_for(target="spontaneous", target_id=act.id)
        assert len(rxs) == 2


class TestSummary:
    def test_glyph_count_aggregates(self, with_spontaneous):
        game, act, _ = with_spontaneous
        game.reactions.react(user_id=game.user("alice").id,
                             target="spontaneous", target_id=act.id, glyph="heart")
        game.reactions.react(user_id=game.user("carol").id,
                             target="spontaneous", target_id=act.id, glyph="heart")
        game.reactions.react(user_id=game.user("bob").id,
                             target="spontaneous", target_id=act.id, glyph="clap")
        summary = game.reactions.summary_for(target="spontaneous", target_id=act.id)
        assert summary == {"heart": 2, "clap": 1}


class TestRemove:
    def test_remove_returns_true_on_hit(self, with_spontaneous):
        game, act, _ = with_spontaneous
        carol = game.user("carol")
        game.reactions.react(user_id=carol.id, target="spontaneous",
                             target_id=act.id, glyph="heart")
        assert game.reactions.remove(
            user_id=carol.id, target="spontaneous", target_id=act.id
        )
        assert game.reactions.list_for(target="spontaneous", target_id=act.id) == []

    def test_remove_missing_returns_false(self, with_spontaneous):
        game, act, _ = with_spontaneous
        assert not game.reactions.remove(
            user_id=game.user("carol").id, target="spontaneous", target_id=act.id
        )


class TestPersistence:
    def test_reactions_survive_save_reload(self, with_spontaneous, tmp_path):
        game, act, _ = with_spontaneous
        carol = game.user("carol")
        game.reactions.react(user_id=carol.id, target="spontaneous",
                             target_id=act.id, glyph="spark")
        game.save()
        # Reload through a fresh Game; should see the reaction.
        from favorgame.game import Game
        reloaded = Game(path=game.repo.path)
        rxs = reloaded.reactions.list_for(target="spontaneous", target_id=act.id)
        assert len(rxs) == 1
        assert rxs[0].glyph == "spark"


class TestOnTransactions:
    def test_can_react_to_paid_transaction(self, with_spontaneous):
        game, _, tx = with_spontaneous
        rx = game.reactions.react(
            user_id=game.user("alice").id, target="transaction",
            target_id=tx.id, glyph="clap",
        )
        assert rx.target.value == "transaction"
        assert rx.target_id == tx.id
