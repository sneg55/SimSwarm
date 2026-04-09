"""Prediction market environment with constant-product AMM.

Ported from MiroShark's Polymarket logic. Supports multiple markets.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from simswarm.types import Action, ActionResult, Agent, Event, Observation, Tool


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
        """Buy NO shares by injecting USD into the YES reserve.

        Adding USD to reserve_yes drives up price_no = reserve_yes / total.
        """
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


@dataclass
class Portfolio:
    balance: float
    shares: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class MarketConfig:
    markets: list[dict[str, Any]]
    initial_balance: float = 1000.0
    initial_liquidity: float = 100.0
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
            market_id = str(uuid.uuid4())
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
            lines.append(f"Market: {market.question} | YES: {market.price_yes:.1%} | NO: {market.price_no:.1%}")
        portfolio = self.portfolios.get(agent.id)
        if portfolio:
            lines.append(f"\nYour balance: ${portfolio.balance:.2f}")
            for mid, shares in portfolio.shares.items():
                m = self.markets.get(mid)
                if m:
                    lines.append(
                        f"  {m.question}: YES={shares.get('yes', 0):.1f}, NO={shares.get('no', 0):.1f}"
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
        outcome = args.get("outcome", "yes")
        amount = args.get("amount", 0.0)
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        if portfolio.balance < amount:
            return ActionResult(success=False, data={"error": "Insufficient balance"})
        market = self.markets[market_id]
        if outcome == "yes":
            shares = market.buy_yes(amount)
        else:
            shares = market.buy_no(amount)
        portfolio.balance -= amount
        if market_id not in portfolio.shares:
            portfolio.shares[market_id] = {"yes": 0.0, "no": 0.0}
        portfolio.shares[market_id][outcome] += shares
        self._trades.append({
            "agent_id": agent.id, "market_id": market_id,
            "side": "buy", "outcome": outcome, "shares": shares,
            "cost": amount, "round": self.current_round,
        })
        return ActionResult(success=True, data={"shares": shares, "cost": amount})

    def _handle_sell(self, agent: Agent, args: dict) -> ActionResult:
        market_id = args.get("market_id", "")
        outcome = args.get("outcome", "yes")
        shares = args.get("shares", 0.0)
        if market_id not in self.markets:
            return ActionResult(success=False, data={"error": "Market not found"})
        portfolio = self.portfolios[agent.id]
        held = portfolio.shares.get(market_id, {}).get(outcome, 0.0)
        if held < shares:
            return ActionResult(success=False, data={"error": "Insufficient shares"})
        market = self.markets[market_id]
        if outcome == "yes":
            usd = market.sell_yes(shares)
        else:
            usd = market.sell_no(shares)
        portfolio.shares[market_id][outcome] -= shares
        portfolio.balance += usd
        self._trades.append({
            "agent_id": agent.id, "market_id": market_id,
            "side": "sell", "outcome": outcome, "shares": shares,
            "usd": usd, "round": self.current_round,
        })
        return ActionResult(success=True, data={"usd": usd})

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
