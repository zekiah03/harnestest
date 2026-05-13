"""Money-movement ledger.

Wrapping each yen+point transfer in a recorded Transaction makes the wallet
balances auditable from history alone, and gives the ranking service a single
spot to derive net flow per user.
"""

from __future__ import annotations

from typing import List, Optional

from favorgame.errors import InsufficientFundsError, NotFoundError
from favorgame.models import Transaction
from favorgame.repository import Repository


class Ledger:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def transfer(
        self,
        *,
        payer_id: int,
        payee_id: int,
        yen_amount: int,
        point_amount: int = 0,
        memo: str = "",
        request_id: Optional[int] = None,
    ) -> Transaction:
        """Move yen (and optional reputation points) from payer to payee."""
        if yen_amount < 0:
            raise ValueError("yen_amount must be >= 0")
        payer = self.repo.get_user(payer_id)
        payee = self.repo.get_user(payee_id)
        if payer.wallet_yen < yen_amount:
            raise InsufficientFundsError(
                f"user {payer.username!r} has {payer.wallet_yen} yen, needs {yen_amount}"
            )
        payer.wallet_yen -= yen_amount
        payee.wallet_yen += yen_amount
        payer.points -= point_amount
        payee.points += point_amount
        tx = Transaction(
            id=self.repo.next_id("transaction"),
            request_id=request_id,
            payer_id=payer_id,
            payee_id=payee_id,
            yen_amount=yen_amount,
            point_amount=point_amount,
            memo=memo,
        )
        self.repo.add_transaction(tx)
        return tx

    def topup(self, user_id: int, yen_amount: int) -> int:
        """Add yen to a user's wallet directly (deposit, not a transfer)."""
        if yen_amount < 0:
            raise ValueError("topup amount must be >= 0")
        try:
            user = self.repo.get_user(user_id)
        except NotFoundError:
            raise
        user.wallet_yen += yen_amount
        return user.wallet_yen

    def history_for(self, user_id: int) -> List[Transaction]:
        return [
            t
            for t in self.repo.list_transactions()
            if t.payer_id == user_id or t.payee_id == user_id
        ]
