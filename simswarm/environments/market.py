"""Prediction-market environment for SimSwarm.

Wraps one or more constant-product :class:`Market` makers and exposes them to
agents as a tool-using environment: agents can browse markets, buy and sell
YES/NO shares against a per-agent cash balance, and comment. Large price swings
are surfaced to the rest of the simulation as cross-environment events.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from simswarm.environments.market_amm import (
    Market,
    SLUG_TOTAL_MAX,
    floor_shares,
    question_to_slug,
    reserves_from_price,
)
from simswarm.environments.market_tools import market_tools
from simswarm.types import Action, ActionResult, Event, Observation, Tool

# Re-exported so callers can import Market from either module.
__all__ = ["Market", "MarketConfig", "MarketEnvironment"]

_ENV_NAME = "market"


@dataclass
class MarketConfig:
    """Environment configuration; every field defaults so ``MarketConfig()`` works."""

    markets: list[dict] = field(default_factory=list)
    initial_balance: float = 1000.0
    initial_liquidity: float = 500.0
    price_move_event_threshold: float = 0.1


@dataclass
class Portfolio:
    """A single agent's cash balance and per-market share holdings."""

    balance: float
    shares: dict = field(default_factory=dict)


class MarketEnvironment:
    def __init__(self, config: MarketConfig):
        self.config = config
        self.markets: dict[str, Market] = {}
        self.portfolios: dict[str, Portfolio] = {}
        self._trades: list[dict] = []
        self._events: list[Event] = []
        self._comments: list[dict] = []
        self._last_price: dict[str, float] = {}
        self._round = 1

        for spec in config.markets:
            question = spec["question"]
            price_yes = spec.get("initial_price_yes", 0.5)
            slug = self._unique_slug(question)
            ry, rn = reserves_from_price(price_yes, config.initial_liquidity)
            self.markets[slug] = Market(
                id=slug, question=question, reserve_yes=ry, reserve_no=rn
            )
            self._last_price[slug] = self.markets[slug].price_yes

    def _unique_slug(self, question: str) -> str:
        base = question_to_slug(question)
        if base not in self.markets:
            return base
        n = 2
        while True:
            suffix = f"_{n}"
            candidate = base[: SLUG_TOTAL_MAX - len(suffix)] + suffix
            if candidate not in self.markets:
                return candidate
            n += 1

    # -- agent lifecycle ----------------------------------------------------

    def register_agent(self, agent) -> None:
        if agent.id not in self.portfolios:
            self.portfolios[agent.id] = Portfolio(
                balance=self.config.initial_balance, shares={}
            )

    def _portfolio(self, agent) -> Portfolio:
        self.register_agent(agent)
        return self.portfolios[agent.id]

    # -- tools --------------------------------------------------------------

    def get_tools(self) -> list[Tool]:
        return market_tools()

    # -- action dispatch ----------------------------------------------------

    def execute_action(self, agent, action: Action) -> ActionResult:
        portfolio = self._portfolio(agent)
        handlers = {
            "buy_shares": self._buy_shares,
            "sell_shares": self._sell_shares,
            "browse_markets": self._browse_markets,
            "comment_on_market": self._comment_on_market,
            "do_nothing": self._do_nothing,
        }
        handler = handlers.get(action.action_type)
        if handler is None:
            return ActionResult(
                success=False,
                data={"error": f"Unknown action: {action.action_type}"},
            )
        return handler(agent, portfolio, action.args or {})

    @staticmethod
    def _normalize_outcome(raw) -> str | None:
        outcome = str(raw).lower()
        return outcome if outcome in ("yes", "no") else None

    def _buy_shares(self, agent, portfolio: Portfolio, args: dict) -> ActionResult:
        market_id = args.get("market_id")
        outcome = self._normalize_outcome(args.get("outcome"))
        amount = args.get("amount", 0.0)

        if outcome is None:
            return ActionResult(
                success=False,
                data={"error": f"invalid outcome: {args.get('outcome')!r}"},
            )
        market = self.markets.get(market_id)
        if market is None:
            return ActionResult(
                success=False, data={"error": f"unknown market: {market_id}"}
            )
        if amount <= 0:
            return ActionResult(
                success=False, data={"error": "amount must be positive"}
            )
        if portfolio.balance < amount:
            return ActionResult(
                success=False, data={"error": "insufficient balance"}
            )

        shares = market.buy_yes(amount) if outcome == "yes" else market.buy_no(amount)
        holding = portfolio.shares.setdefault(market_id, {"yes": 0.0, "no": 0.0})
        holding[outcome] = holding.get(outcome, 0.0) + shares
        portfolio.balance -= amount

        data = {
            "side": "buy",
            "market_id": market_id,
            "outcome": outcome,
            "shares": shares,
            "cost": amount,
            "price": market.price_yes,
            "round": self._round,
        }
        self._trades.append(dict(data))
        return ActionResult(success=True, data=data)

    def _sell_shares(self, agent, portfolio: Portfolio, args: dict) -> ActionResult:
        market_id = args.get("market_id")
        outcome = self._normalize_outcome(args.get("outcome"))
        shares = args.get("shares", 0.0)

        if outcome is None:
            return ActionResult(
                success=False,
                data={"error": f"invalid outcome: {args.get('outcome')!r}"},
            )
        market = self.markets.get(market_id)
        if market is None:
            return ActionResult(
                success=False, data={"error": f"unknown market: {market_id}"}
            )
        if shares <= 0:
            return ActionResult(
                success=False, data={"error": "shares must be positive"}
            )

        held = portfolio.shares.get(market_id, {}).get(outcome, 0.0)
        if held < shares:
            return ActionResult(
                success=False,
                data={"error": "insufficient shares", "held": held},
            )

        proceeds = (
            market.sell_yes(shares) if outcome == "yes" else market.sell_no(shares)
        )
        portfolio.balance += proceeds
        portfolio.shares[market_id][outcome] = held - shares

        data = {
            "side": "sell",
            "market_id": market_id,
            "outcome": outcome,
            "shares": shares,
            "proceeds": proceeds,
            "price": market.price_yes,
            "round": self._round,
        }
        self._trades.append(dict(data))
        return ActionResult(success=True, data=data)

    def _comment_on_market(self, agent, portfolio: Portfolio, args: dict) -> ActionResult:
        market_id = args.get("market_id")
        text = args.get("text", "")
        self._comments.append(
            {"agent_id": agent.id, "market_id": market_id, "text": text}
        )
        return ActionResult(
            success=True,
            data={"action": "comment", "market_id": market_id, "text": text},
        )

    def _browse_markets(self, agent, portfolio: Portfolio, args: dict) -> ActionResult:
        listing = [
            {
                "market_id": m.id,
                "question": m.question,
                "price_yes": m.price_yes,
                "price_no": m.price_no,
            }
            for m in self.markets.values()
        ]
        return ActionResult(success=True, data={"markets": listing})

    def _do_nothing(self, agent, portfolio: Portfolio, args: dict) -> ActionResult:
        return ActionResult(success=True, data={})

    # -- observations -------------------------------------------------------

    def get_observations(self, agent) -> Observation:
        portfolio = self._portfolio(agent)
        lines = []
        for m in self.markets.values():
            lines.append(
                f"Market [{m.id}]: {m.question} | "
                f"YES: {m.price_yes * 100:.0f}% | NO: {m.price_no * 100:.0f}%"
            )
            holding = portfolio.shares.get(m.id, {})
            yes_held = floor_shares(holding.get("yes", 0.0))
            no_held = floor_shares(holding.get("no", 0.0))
            lines.append(
                f"  Your position in [{m.id}]: YES={yes_held} NO={no_held}"
            )
        return Observation(environment=_ENV_NAME, content="\n".join(lines))

    # -- event lifecycle ----------------------------------------------------

    def tick(self) -> None:
        for slug, market in self.markets.items():
            current = market.price_yes
            previous = self._last_price.get(slug, current)
            if abs(current - previous) >= self.config.price_move_event_threshold:
                self._events.append(
                    Event(
                        source=_ENV_NAME,
                        type="price_move",
                        data={
                            "market_id": slug,
                            "from": previous,
                            "to": current,
                        },
                        round=self._round,
                    )
                )
            self._last_price[slug] = current
        self._round += 1

    def publish_events(self) -> list[Event]:
        events = self._events
        self._events = []
        return events
