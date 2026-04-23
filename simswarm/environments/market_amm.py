"""Constant-product AMM primitives for prediction markets.

Ported from MiroShark's Polymarket logic. Pure math — no env/agent coupling.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Market:
    """A single prediction market with AMM pricing."""
    id: str
    question: str
    reserve_yes: float
    reserve_no: float

    @property
    def price_yes(self) -> float:
        return self.reserve_no / (self.reserve_yes + self.reserve_no)

    @property
    def price_no(self) -> float:
        return self.reserve_yes / (self.reserve_yes + self.reserve_no)

    def buy_yes(self, usd: float) -> float:
        """Buy YES shares by injecting USD into the NO reserve.

        Adding USD to reserve_no drives up price_yes = reserve_no / total.
        Constant-product k = reserve_yes * reserve_no is preserved.
        """
        k = self.reserve_yes * self.reserve_no
        new_reserve_no = self.reserve_no + usd
        new_reserve_yes = k / new_reserve_no
        shares = self.reserve_yes - new_reserve_yes
        self.reserve_yes = new_reserve_yes
        self.reserve_no = new_reserve_no
        return shares

    def buy_no(self, usd: float) -> float:
        """Buy NO shares by injecting USD into the YES reserve."""
        k = self.reserve_yes * self.reserve_no
        new_reserve_yes = self.reserve_yes + usd
        new_reserve_no = k / new_reserve_yes
        shares = self.reserve_no - new_reserve_no
        self.reserve_yes = new_reserve_yes
        self.reserve_no = new_reserve_no
        return shares

    def sell_yes(self, shares: float) -> float:
        """Return YES shares to the pool, receive USD from the NO reserve."""
        k = self.reserve_yes * self.reserve_no
        new_reserve_yes = self.reserve_yes + shares
        new_reserve_no = k / new_reserve_yes
        usd = self.reserve_no - new_reserve_no
        self.reserve_yes = new_reserve_yes
        self.reserve_no = new_reserve_no
        return usd

    def sell_no(self, shares: float) -> float:
        """Return NO shares to the pool, receive USD from the YES reserve."""
        k = self.reserve_yes * self.reserve_no
        new_reserve_no = self.reserve_no + shares
        new_reserve_yes = k / new_reserve_no
        usd = self.reserve_yes - new_reserve_yes
        self.reserve_yes = new_reserve_yes
        self.reserve_no = new_reserve_no
        return usd
