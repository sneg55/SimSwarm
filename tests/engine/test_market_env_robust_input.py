"""Robustness tests for MarketEnvironment handler inputs.

Sim 124 round 16 crashed with `KeyError: 'YES'` because the LLM sent
`outcome="YES"` (uppercase) into sell_shares — the portfolio was
initialized with lowercase keys in buy, and the sell handler dereferenced
the raw `outcome` without normalization. These tests pin the contract:
handlers normalize outcome case and fail gracefully, never crash.
"""
from __future__ import annotations

import pytest

from simswarm.environments.market import MarketEnvironment, MarketConfig
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Trader") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test trader",
        environments=["market"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


def test_sell_normalizes_outcome_case():
    """outcome='YES' must behave identically to outcome='yes'."""
    env = MarketEnvironment(MarketConfig(
        markets=[{"question": "Test?", "initial_price_yes": 0.5}],
        initial_balance=1000.0,
    ))
    trader = _make_agent("t1")
    env.register_agent(trader)
    mid = list(env.markets.keys())[0]
    buy = env.execute_action(trader, Action(
        agent_id="t1", environment="market", action_type="buy_shares",
        args={"market_id": mid, "outcome": "yes", "amount": 50.0},
    ))
    held = env.portfolios["t1"].shares[mid]["yes"]
    # Sell the full position via the UPPERCASE alias.
    sell = env.execute_action(trader, Action(
        agent_id="t1", environment="market", action_type="sell_shares",
        args={"market_id": mid, "outcome": "YES", "shares": held},
    ))
    assert buy.success
    assert sell.success, f"sell with uppercase outcome failed: {sell.data}"
    assert env.portfolios["t1"].shares[mid]["yes"] == pytest.approx(0.0)


def test_sell_rejects_unknown_outcome_without_crash():
    """Any outcome that isn't yes/no gets a failed ActionResult — never raises."""
    env = MarketEnvironment(MarketConfig(
        markets=[{"question": "Test?", "initial_price_yes": 0.5}],
    ))
    trader = _make_agent("t1")
    env.register_agent(trader)
    mid = list(env.markets.keys())[0]
    result = env.execute_action(trader, Action(
        agent_id="t1", environment="market", action_type="sell_shares",
        args={"market_id": mid, "outcome": "maybe", "shares": 5.0},
    ))
    assert result.success is False
    assert "outcome" in result.data.get("error", "").lower()


def test_sell_with_zero_shares_no_keyerror():
    """shares=0 and a never-initialized portfolio entry must not crash.

    Covers the exact path that took sim 124 down: held=0, shares=0,
    `held < shares` is False, and the old code then did
    `portfolio.shares[mid][outcome] -= 0` which raised KeyError if the
    outcome key was missing.
    """
    env = MarketEnvironment(MarketConfig(
        markets=[{"question": "Test?", "initial_price_yes": 0.5}],
    ))
    trader = _make_agent("t1")
    env.register_agent(trader)
    mid = list(env.markets.keys())[0]
    result = env.execute_action(trader, Action(
        agent_id="t1", environment="market", action_type="sell_shares",
        args={"market_id": mid, "outcome": "yes", "shares": 0.0},
    ))
    # Whatever the policy (reject / no-op), it MUST not raise.
    assert result.success is False


def test_buy_normalizes_outcome_case():
    """Same normalization on the buy side — LLMs send 'YES' into buy too."""
    env = MarketEnvironment(MarketConfig(
        markets=[{"question": "Test?", "initial_price_yes": 0.5}],
        initial_balance=1000.0,
    ))
    trader = _make_agent("t1")
    env.register_agent(trader)
    mid = list(env.markets.keys())[0]
    result = env.execute_action(trader, Action(
        agent_id="t1", environment="market", action_type="buy_shares",
        args={"market_id": mid, "outcome": "YES", "amount": 50.0},
    ))
    assert result.success, f"buy with uppercase outcome failed: {result.data}"
    assert env.portfolios["t1"].shares[mid]["yes"] > 0
