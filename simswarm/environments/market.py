"""Prediction market environment with constant-product AMM.

Ported from MiroShark's Polymarket logic. Supports multiple markets.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from simswarm.environments.market_amm import Market
from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


_SLUG_MAX_LEN = 40
_SHARE_EPSILON = 1e-6


def _floor_1dp(x: float) -> float:
    """Floor to 1 decimal place so observation never advertises more than held."""
    return math.floor(x * 10) / 10


def _question_to_slug(question: str, existing: set[str]) -> str:
    """Derive a short deterministic market_id from the question.

    Lowercase; non-alphanumerics become underscores; collapse repeats; trim; cap.
    Collides → numeric suffix. Exposed in observations so the LLM can reference
    markets by id in buy_shares/sell_shares calls.
    """
    base = re.sub(r"[^a-z0-9]+", "_", question.lower()).strip("_")[:_SLUG_MAX_LEN] or "market"
    slug = base
    n = 2
    while slug in existing:
        slug = f"{base}_{n}"
        n += 1
    return slug


@dataclass
class Portfolio:
    balance: float
    shares: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class MarketConfig:
    markets: list[dict[str, Any]] = field(default_factory=list)
    initial_balance: float = 1000.0
    # Liquidity governs AMM depth. With 20 agents × $1000 balance, liquidity=100
    # let a single one-sided round peg YES to ~0% / ~100% and agents then
    # endlessly post about the pegged price (sim 127). 500 still allows
    # meaningful price moves but keeps prices in ~[10%, 90%] under consensus.
    initial_liquidity: float = 500.0
    price_move_event_threshold: float = 0.1


class MarketEnvironment:
    name = "market"

    def __init__(self, config: MarketConfig, current_round: int = 0):
        self.config = config
        self.current_round = current_round
        self.markets: dict[str, Market] = {}
        self.portfolios: dict[str, Portfolio] = {}
        self._pending_events: list[Event] = []
        self._last_prices: dict[str, float] = {}
        self._trades: list[dict] = []

        for m in config.markets:
            market_id = _question_to_slug(m["question"], set(self.markets))
            price_yes = m.get("initial_price_yes", 0.5)
            liq = config.initial_liquidity
            reserve_yes = liq * 2 * (1 - price_yes)
            reserve_no = liq * 2 * price_yes
            self.markets[market_id] = Market(
                id=market_id, question=m["question"],
                reserve_yes=reserve_yes, reserve_no=reserve_no,
            )
            self._last_prices[market_id] = price_yes

    def register_agent(self, agent: Agent) -> None:
        if agent.id not in self.portfolios:
            self.portfolios[agent.id] = Portfolio(balance=self.config.initial_balance)

    def execute_action(self, agent: Agent, action: Action) -> ActionResult:
        self.register_agent(agent)
        handler = {
            "buy_shares": self._handle_buy,
            "sell_shares": self._handle_sell,
            "browse_markets": self._handle_browse,
            "comment_on_market": self._handle_comment,
            "do_nothing": self._handle_noop,
        }.get(action.action_type)
        if handler is None:
            return ActionResult(success=False, data={"error": f"Unknown action: {action.action_type}"})
        return handler(agent, action.args)

    def get_observations(self, agent: Agent) -> Observation:
        self.register_agent(agent)
        lines = []
        for market in self.markets.values():
            lines.append(
                f"Market [{market.id}]: {market.question} "
                f"| YES: {market.price_yes:.1%} | NO: {market.price_no:.1%}"
            )
        portfolio = self.portfolios.get(agent.id)
        if portfolio:
            lines.append(f"\nYour balance: ${portfolio.balance:.2f}")
            for mid, shares in portfolio.shares.items():
                m = self.markets.get(mid)
                if m:
                    lines.append(
                        f"  {m.question}: "
                        f"YES={_floor_1dp(shares.get('yes', 0)):.1f}, "
                        f"NO={_floor_1dp(shares.get('no', 0)):.1f}"
                    )
        content = "\n".join(lines) if lines else "(no markets)"
        return Observation(environment=self.name, content=content)

    def get_tools(self) -> list[Tool]:
        return [
            Tool(name="buy_shares", description="Buy outcome shares in a market",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"},
                     "outcome": {"type": "string", "enum": ["yes", "no"]},
                     "amount": {"type": "number", "description": "USD to spend"},
                 }, "required": ["market_id", "outcome", "amount"]}),
            Tool(name="sell_shares", description="Sell outcome shares",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"},
                     "outcome": {"type": "string", "enum": ["yes", "no"]},
                     "shares": {"type": "number"},
                 }, "required": ["market_id", "outcome", "shares"]}),
            Tool(name="browse_markets", description="View all available markets",
                 parameters={"type": "object", "properties": {}}),
            Tool(name="comment_on_market", description="Comment on a market",
                 parameters={"type": "object", "properties": {
                     "market_id": {"type": "string"}, "text": {"type": "string"},
                 }, "required": ["market_id", "text"]}),
            Tool(name="do_nothing", description="Take no action",
                 parameters={"type": "object", "properties": {}}),
        ]

    def publish_events(self) -> list[Event]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def tick(self) -> None:
        self.current_round += 1
        for market_id, market in self.markets.items():
            prev = self._last_prices.get(market_id, 0.5)
            curr = market.price_yes
            delta = abs(curr - prev)
            if delta >= self.config.price_move_event_threshold:
                self._pending_events.append(Event(
                    source=self.name, type="price_move",
                    data={"market_id": market_id, "question": market.question,
                          "price_yes": curr, "delta": curr - prev},
                    round=self.current_round,
                ))
            self._last_prices[market_id] = curr

    def _handle_buy(self, agent: Agent, args: dict) -> ActionResult:
        market_id = args.get("market_id", "")
        outcome = str(args.get("outcome", "yes")).strip().lower()
        amount = args.get("amount", 0.0)
        if outcome not in ("yes", "no"):
            return ActionResult(
                success=False,
                data={"error": f"Invalid outcome: {outcome!r} (expected 'yes' or 'no')"},
            )
        if amount <= 0:
            return ActionResult(success=False, data={"error": "amount must be positive"})
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        if portfolio.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})
        market = self.markets[market_id]
        if outcome == "yes":
            shares = market.buy_yes(amount)
            executed_price = market.price_yes
        else:
            shares = market.buy_no(amount)
            executed_price = market.price_no
        portfolio.balance -= amount
        if market_id not in portfolio.shares:
            portfolio.shares[market_id] = {"yes": 0.0, "no": 0.0}
        portfolio.shares[market_id][outcome] += shares
        trade = {
            "market_id": market_id, "outcome": outcome,
            "shares": shares, "cost": amount, "price": executed_price,
            "round": self.current_round,
        }
        self._trades.append({"agent_id": agent.id, "side": "buy", **trade})
        return ActionResult(success=True, data={"side": "buy", **trade})

    def _handle_sell(self, agent: Agent, args: dict) -> ActionResult:
        market_id = args.get("market_id", "")
        outcome = str(args.get("outcome", "yes")).strip().lower()
        shares = args.get("shares", 0.0)
        if outcome not in ("yes", "no"):
            return ActionResult(
                success=False,
                data={"error": f"Invalid outcome: {outcome!r} (expected 'yes' or 'no')"},
            )
        if shares <= 0:
            return ActionResult(success=False, data={"error": "shares must be positive"})
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        held = portfolio.shares.get(market_id, {}).get(outcome, 0.0)
        if held <= _SHARE_EPSILON:
            return ActionResult(success=False, data={"error": "Insufficient shares"})
        # Cap at held so rounded-up observation values (e.g. 1.994 shown as 2.0)
        # don't trip a strict inequality. See market env rounding regression.
        shares = min(shares, held)
        market = self.markets[market_id]
        if outcome == "yes":
            proceeds = market.sell_yes(shares)
            executed_price = market.price_yes
        else:
            proceeds = market.sell_no(shares)
            executed_price = market.price_no
        portfolio.shares[market_id][outcome] -= shares
        portfolio.balance += proceeds
        trade = {
            "market_id": market_id, "outcome": outcome,
            "shares": shares, "proceeds": proceeds, "price": executed_price,
            "round": self.current_round,
        }
        self._trades.append({"agent_id": agent.id, "side": "sell", **trade})
        return ActionResult(success=True, data={"side": "sell", **trade})

    def _handle_browse(self, agent: Agent, args: dict) -> ActionResult:
        data = []
        for m in self.markets.values():
            data.append({"market_id": m.id, "question": m.question,
                         "price_yes": m.price_yes, "price_no": m.price_no})
        return ActionResult(success=True, data={"markets": data})

    def _handle_comment(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})

    def _handle_noop(self, agent: Agent, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})
