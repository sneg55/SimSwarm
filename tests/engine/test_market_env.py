"""Test prediction market environment: AMM pricing, buy/sell, portfolio tracking."""
from __future__ import annotations

import pytest

from simswarm.environments.market import MarketEnvironment, MarketConfig, Market
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Trader") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test trader",
        environments=["market"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestAMMPricing:
    def test_initial_price_at_fifty_percent(self):
        market = Market(id="m1", question="Will X happen?", reserve_yes=100, reserve_no=100)
        assert market.price_yes == pytest.approx(0.5)
        assert market.price_no == pytest.approx(0.5)

    def test_prices_sum_to_one(self):
        market = Market(id="m1", question="?", reserve_yes=150, reserve_no=50)
        assert market.price_yes + market.price_no == pytest.approx(1.0)

    def test_buy_yes_increases_yes_price(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        initial_price = market.price_yes
        market.buy_yes(10.0)
        assert market.price_yes > initial_price

    def test_buy_no_increases_no_price(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        initial_price = market.price_no
        market.buy_no(10.0)
        assert market.price_no > initial_price


class TestBuySell:
    def test_buy_returns_shares(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        shares = market.buy_yes(10.0)
        assert shares > 0

    def test_sell_returns_usd(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        shares = market.buy_yes(10.0)
        usd = market.sell_yes(shares)
        assert usd > 0
        assert usd == pytest.approx(10.0, rel=0.01)

    def test_constant_product_invariant_after_buy(self):
        market = Market(id="m1", question="?", reserve_yes=100, reserve_no=100)
        k_before = market.reserve_yes * market.reserve_no
        market.buy_yes(10.0)
        k_after = market.reserve_yes * market.reserve_no
        assert k_after == pytest.approx(k_before, rel=0.001)


class TestPortfolio:
    def test_buy_updates_portfolio(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Test?", "initial_price_yes": 0.5}],
            initial_balance=1000.0,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)
        market_id = list(env.markets.keys())[0]
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": market_id, "outcome": "yes", "amount": 50.0},
        ))
        assert result.success
        portfolio = env.portfolios["t1"]
        assert portfolio.balance < 1000.0
        assert portfolio.shares.get(market_id, {}).get("yes", 0) > 0


class TestMultipleMarkets:
    def test_supports_multiple_markets(self):
        env = MarketEnvironment(MarketConfig(
            markets=[
                {"question": "Will A happen?", "initial_price_yes": 0.6},
                {"question": "Will B happen?", "initial_price_yes": 0.4},
            ],
            initial_balance=1000.0,
        ))
        assert len(env.markets) == 2


class TestMarketEvents:
    def test_large_price_move_publishes_event(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Test?", "initial_price_yes": 0.5}],
            initial_balance=10000.0,
            price_move_event_threshold=0.05,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)
        market_id = list(env.markets.keys())[0]
        env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": market_id, "outcome": "yes", "amount": 500.0},
        ))
        env.tick()
        events = env.publish_events()
        price_events = [e for e in events if e.type == "price_move"]
        assert len(price_events) >= 1


class TestMarketTools:
    def test_get_tools_returns_expected_actions(self):
        env = MarketEnvironment(MarketConfig(markets=[], initial_balance=100.0))
        tools = env.get_tools()
        tool_names = {t.name for t in tools}
        assert "buy_shares" in tool_names
        assert "sell_shares" in tool_names
        assert "browse_markets" in tool_names


class TestActionResultShape:
    """Buy and sell return a consistent ActionResult.data schema."""

    def _env(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Will X?", "initial_price_yes": 0.5}],
            initial_balance=1000.0,
        ))
        trader = _make_agent("t1")
        env.register_agent(trader)
        return env, trader, list(env.markets.keys())[0]

    def test_buy_data_shape(self):
        env, trader, mid = self._env()
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": mid, "outcome": "yes", "amount": 50.0},
        ))
        assert result.success
        data = result.data
        assert data["side"] == "buy"
        assert data["market_id"] == mid
        assert data["outcome"] == "yes"
        assert data["cost"] == pytest.approx(50.0)
        assert data["shares"] > 0
        assert 0 < data["price"] < 1

    def test_sell_data_shape(self):
        env, trader, mid = self._env()
        env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": mid, "outcome": "yes", "amount": 50.0},
        ))
        held = env.portfolios["t1"].shares[mid]["yes"]
        result = env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="sell_shares",
            args={"market_id": mid, "outcome": "yes", "shares": held / 2},
        ))
        assert result.success
        data = result.data
        assert data["side"] == "sell"
        assert data["market_id"] == mid
        assert data["outcome"] == "yes"
        assert data["proceeds"] > 0
        assert data["shares"] == pytest.approx(held / 2)
        assert 0 < data["price"] < 1

    def test_internal_trades_list_also_normalized(self):
        env, trader, mid = self._env()
        env.execute_action(trader, Action(
            agent_id="t1", environment="market",
            action_type="buy_shares",
            args={"market_id": mid, "outcome": "yes", "amount": 50.0},
        ))
        assert len(env._trades) == 1
        t = env._trades[0]
        assert t["side"] == "buy"
        assert t["cost"] == pytest.approx(50.0)
        assert "price" in t


class TestMarketIdSlug:
    """Market IDs must be deterministic slugs derived from the question,
    and observations must expose them so the LLM can reference them."""

    def test_slug_from_question(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Will the Fed cut by 50bp?"}],
        ))
        mid = list(env.markets.keys())[0]
        assert mid == "will_the_fed_cut_by_50bp"

    def test_slug_truncated_and_collision_suffixed(self):
        env = MarketEnvironment(MarketConfig(markets=[
            {"question": "Will the Fed cut rates by exactly 50bp at May 7, 2026 FOMC meeting?"},
            {"question": "Will the Fed cut rates by exactly 25bp at May 7, 2026 FOMC meeting?"},
        ]))
        ids = list(env.markets.keys())
        assert len(ids) == 2
        assert len(set(ids)) == 2  # unique
        for mid in ids:
            assert len(mid) <= 45  # slug max + collision suffix slack

    def test_observation_includes_market_id(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Will X?"}],
        ))
        trader = _make_agent("t1")
        obs = env.get_observations(trader)
        mid = list(env.markets.keys())[0]
        assert mid in obs.content
        assert "Will X?" in obs.content


class TestRoundingConsistency:
    """Observation must not advertise more shares than the agent can actually sell.

    Regression: :.1f formatting rounds 1.994 -> "2.0"; LLM copies "2.0" into a
    sell_shares call; sell handler rejects because true held (1.994) < 2.0.
    """

    def _setup(self):
        env = MarketEnvironment(MarketConfig(
            markets=[{"question": "Will X?"}],
            initial_balance=10_000.0,
            initial_liquidity=100.0,
        ))
        agent = _make_agent("a1")
        env.register_agent(agent)
        mid = list(env.markets.keys())[0]
        # Force portfolio into a known fractional holding.
        env.portfolios[agent.id].shares[mid] = {"yes": 0.0, "no": 1.994}
        return env, agent, mid

    def test_observation_does_not_round_up_past_held(self):
        env, agent, _ = self._setup()
        obs = env.get_observations(agent).content
        # Extract the NO=... token and verify displayed value <= true held.
        import re
        m = re.search(r"NO=([0-9.]+)", obs)
        assert m, f"no NO=... token in {obs!r}"
        displayed = float(m.group(1))
        assert displayed <= 1.994, f"observation rounded up past held: {displayed}"

    def test_sell_accepts_value_from_observation(self):
        env, agent, mid = self._setup()
        obs = env.get_observations(agent).content
        import re
        m = re.search(r"NO=([0-9.]+)", obs)
        displayed = float(m.group(1))
        result = env.execute_action(
            agent,
            Action(agent_id=agent.id, environment="market",
                   action_type="sell_shares",
                   args={"market_id": mid, "outcome": "no", "shares": displayed}),
        )
        assert result.success, f"sell of displayed balance failed: {result.data}"
