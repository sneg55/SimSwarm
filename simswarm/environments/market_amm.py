"""Constant-product automated market maker for binary prediction markets.

A :class:`Market` holds two reserves — one backing YES shares, one backing NO
shares. The instantaneous price of an outcome is the *opposite* reserve's
fraction of the total pool, so prices always sum to 1. Trades hold the product
``reserve_yes * reserve_no`` constant (Uniswap-style x*y=k), which makes each
buy push its outcome's price up and each sell pull it back down.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Slug derivation bounds for market identifiers.
SLUG_BASE_MAX = 40
SLUG_TOTAL_MAX = 45


def question_to_slug(question: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to '_', strip, cap length."""
    base = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")
    return base[:SLUG_BASE_MAX]


def floor_shares(value: float) -> float:
    """Floor a holding to 2 decimals so a displayed value is never > true held."""
    return math.floor(value * 100) / 100


@dataclass
class Market:
    """A single binary YES/NO market backed by two reserves."""

    id: str
    question: str
    reserve_yes: float
    reserve_no: float

    @property
    def _pool(self) -> float:
        return self.reserve_yes + self.reserve_no

    @property
    def price_yes(self) -> float:
        return self.reserve_no / self._pool

    @property
    def price_no(self) -> float:
        return self.reserve_yes / self._pool

    def buy_yes(self, amount: float) -> float:
        """Spend `amount` of collateral on YES shares; return shares acquired."""
        k = self.reserve_yes * self.reserve_no
        new_no = self.reserve_no + amount
        new_yes = k / new_no
        shares = self.reserve_yes - new_yes
        self.reserve_yes = new_yes
        self.reserve_no = new_no
        return shares

    def buy_no(self, amount: float) -> float:
        """Spend `amount` of collateral on NO shares; return shares acquired."""
        k = self.reserve_yes * self.reserve_no
        new_yes = self.reserve_yes + amount
        new_no = k / new_yes
        shares = self.reserve_no - new_no
        self.reserve_no = new_no
        self.reserve_yes = new_yes
        return shares

    def sell_yes(self, shares: float) -> float:
        """Return `shares` of YES to the pool; return collateral proceeds."""
        k = self.reserve_yes * self.reserve_no
        new_yes = self.reserve_yes + shares
        new_no = k / new_yes
        proceeds = self.reserve_no - new_no
        self.reserve_yes = new_yes
        self.reserve_no = new_no
        return proceeds

    def sell_no(self, shares: float) -> float:
        """Return `shares` of NO to the pool; return collateral proceeds."""
        k = self.reserve_yes * self.reserve_no
        new_no = self.reserve_no + shares
        new_yes = k / new_no
        proceeds = self.reserve_yes - new_yes
        self.reserve_no = new_no
        self.reserve_yes = new_yes
        return proceeds


def reserves_from_price(price_yes: float, liquidity: float) -> tuple[float, float]:
    """Derive (reserve_yes, reserve_no) seeding a market at the given price.

    Because price_yes = reserve_no / pool, a higher seed price means a smaller
    YES reserve. Total pool is 2 * liquidity, so equal 0.5 splits land at
    (liquidity, liquidity).
    """
    reserve_yes = liquidity * 2 * (1 - price_yes)
    reserve_no = liquidity * 2 * price_yes
    return reserve_yes, reserve_no
