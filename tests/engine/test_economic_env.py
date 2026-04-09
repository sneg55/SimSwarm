"""Test economic environment: actor registration and action handling."""
from __future__ import annotations

import pytest

from simswarm.environments.economic import EconomicEnvironment, EconomicConfig
from simswarm.types import Action, Agent, AgentActivityConfig, BeliefState


def _make_agent(agent_id: str, name: str = "Firm") -> Agent:
    return Agent(
        id=agent_id, name=name, persona="Test firm",
        environments=["economic"], belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


class TestRegisterAgent:
    def test_register_creates_actor(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1", "FirmA")
        env.register_agent(agent, role="producer", balance=500.0)
        assert "f1" in env.actors
        actor = env.actors["f1"]
        assert actor.role == "producer"
        assert actor.balance == 500.0

    def test_register_twice_is_idempotent(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=100.0)
        env.register_agent(agent, role="producer", balance=999.0)
        assert env.actors["f1"].balance == 100.0  # first registration wins


class TestSetPrice:
    def test_set_price_updates_actor(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="set_price", args={"price": 42.0},
        ))
        assert result.success
        assert env.actors["f1"].price == 42.0

    def test_set_price_reflects_in_metrics_after_tick(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="set_price", args={"price": 100.0},
        ))
        env.tick()
        assert env.metrics["avg_price"] == pytest.approx(100.0)


class TestHire:
    def test_hire_increases_workforce(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 10},
        ))
        assert result.success
        assert env.actors["f1"].workforce == 10

    def test_hire_updates_employment_rate_after_tick(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=100))
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=1000.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 50},
        ))
        env.tick()
        assert env.metrics["employment_rate"] == pytest.approx(0.5)


class TestFire:
    def test_fire_reduces_workforce(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 20},
        ))
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="fire", args={"count": 8},
        ))
        assert result.success
        assert env.actors["f1"].workforce == 12

    def test_fire_cannot_go_below_zero(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="fire", args={"count": 100},
        ))
        assert not result.success
        assert "error" in result.data
        assert env.actors["f1"].workforce == 0


class TestInvest:
    def test_invest_transfers_balance_to_output(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="invest", args={"amount": 200.0},
        ))
        assert result.success
        actor = env.actors["f1"]
        assert actor.balance == pytest.approx(300.0)
        assert actor.output == pytest.approx(200.0)

    def test_invest_insufficient_balance_fails(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=100.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="invest", args={"amount": 500.0},
        ))
        assert not result.success
        assert "error" in result.data

    def test_invest_accumulates_in_total_investment_metric(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=1000.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="invest", args={"amount": 300.0},
        ))
        env.tick()
        assert env.metrics["total_investment"] == pytest.approx(300.0)


class TestPoliciesAndMisc:
    def test_allocate_succeeds(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="government", balance=1000.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="allocate", args={"target": "infrastructure", "amount": 50.0},
        ))
        assert result.success

    def test_apply_policy_records_in_active_policies(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("gov")
        env.register_agent(agent, role="government", balance=10000.0)
        result = env.execute_action(agent, Action(
            agent_id="gov", environment="economic",
            action_type="apply_policy",
            args={"policy_name": "tax_cut", "description": "Reduce corporate tax"},
        ))
        assert result.success
        assert "tax_cut" in [p["name"] for p in env.active_policies]

    def test_apply_policy_injects_scenario_variable(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("gov")
        env.register_agent(agent, role="government", balance=10000.0)
        env.execute_action(agent, Action(
            agent_id="gov", environment="economic",
            action_type="apply_policy",
            args={"policy_name": "min_wage_hike", "description": "Raise minimum wage",
                  "variable": "min_wage", "value": 15.0},
        ))
        assert env.scenario_variables.get("min_wage") == pytest.approx(15.0)

    def test_do_nothing_succeeds(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=100.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="do_nothing", args={},
        ))
        assert result.success

    def test_unknown_action_returns_error(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=100.0)
        result = env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="teleport", args={},
        ))
        assert not result.success
        assert "error" in result.data
