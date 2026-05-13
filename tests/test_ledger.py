"""Tests for the Ledger."""

import pytest

from favorgame.errors import InsufficientFundsError, NotFoundError


def test_topup_adds_to_wallet(populated_game):
    alice = populated_game.user("alice")
    new_balance = populated_game.ledger.topup(alice.id, 500)
    assert new_balance == 1500
    assert alice.wallet_yen == 1500


def test_topup_negative_rejected(populated_game):
    alice = populated_game.user("alice")
    with pytest.raises(ValueError):
        populated_game.ledger.topup(alice.id, -1)


def test_topup_unknown_user(populated_game):
    with pytest.raises(NotFoundError):
        populated_game.ledger.topup(99, 100)


def test_transfer_moves_yen_and_points(populated_game):
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    populated_game.ledger.transfer(
        payer_id=alice.id, payee_id=bob.id,
        yen_amount=200, point_amount=5, memo="test"
    )
    assert alice.wallet_yen == 800
    assert bob.wallet_yen == 1200
    assert alice.points == -5
    assert bob.points == 5


def test_transfer_insufficient_funds(populated_game):
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    with pytest.raises(InsufficientFundsError):
        populated_game.ledger.transfer(
            payer_id=alice.id, payee_id=bob.id, yen_amount=99_999
        )


def test_transfer_records_transaction(populated_game):
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    populated_game.ledger.transfer(
        payer_id=alice.id, payee_id=bob.id, yen_amount=200, point_amount=5
    )
    txs = populated_game.ledger.history_for(alice.id)
    assert len(txs) == 1
    assert txs[0].yen_amount == 200
    assert txs[0].point_amount == 5


def test_history_includes_both_directions(populated_game):
    alice = populated_game.user("alice")
    bob = populated_game.user("bob")
    populated_game.ledger.transfer(payer_id=alice.id, payee_id=bob.id, yen_amount=100)
    populated_game.ledger.transfer(payer_id=bob.id, payee_id=alice.id, yen_amount=50)
    assert len(populated_game.ledger.history_for(alice.id)) == 2
    assert len(populated_game.ledger.history_for(bob.id)) == 2
