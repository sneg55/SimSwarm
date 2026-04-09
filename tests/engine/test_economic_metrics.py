"""Test economic environment: aggregate metrics, events, observations, and tools."""
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


class TestAggregateMetrics:
    def test_avg_price_across_multiple_firms(self):
        env = EconomicEnvironment(EconomicConfig())
        a1 = _make_agent("f1", "Firm1")
        a2 = _make_agent("f2", "Firm2")
        env.register_agent(a1, role="producer", balance=500.0)
        env.register_agent(a2, role="producer", balance=500.0)
        env.execute_action(a1, Action(
            agent_id="f1", environment="economic",
            action_type="set_price", args={"price": 10.0},
        ))
        env.execute_action(a2, Action(
            agent_id="f2", environment="economic",
            action_type="set_price", args={"price": 30.0},
        ))
        env.tick()
        assert env.metrics["avg_price"] == pytest.approx(20.0)

    def test_employment_rate_capped_at_one(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=10))
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=1000.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 100},
        ))
        env.tick()
        assert env.metrics["employment_rate"] <= 1.0

    def test_total_output_sums_across_actors(self):
        env = EconomicEnvironment(EconomicConfig())
        a1 = _make_agent("f1")
        a2 = _make_agent("f2")
        env.register_agent(a1, role="producer", balance=1000.0)
        env.register_agent(a2, role="producer", balance=1000.0)
        env.execute_action(a1, Action(
            agent_id="f1", environment="economic",
            action_type="invest", args={"amount": 100.0},
        ))
        env.execute_action(a2, Action(
            agent_id="f2", environment="economic",
            action_type="invest", args={"amount": 200.0},
        ))
        env.tick()
        assert env.metrics["total_output"] == pytest.approx(300.0)


class TestMetricChangeEvents:
    def test_significant_employment_change_publishes_event(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=100, metric_change_threshold=0.05))
        # Tick once to seed last metrics
        env.tick()
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=1000.0)
        # Hire 20 workers = 20% employment rate, well above 5% threshold
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 20},
        ))
        env.tick()
        events = env.publish_events()
        metric_events = [e for e in events if e.type == "metric_change"]
        assert len(metric_events) >= 1

    def test_small_change_does_not_publish_event(self):
        env = EconomicEnvironment(EconomicConfig(labor_force=10000, metric_change_threshold=0.05))
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=1000.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 1},
        ))
        env.tick()
        env.publish_events()  # clear first-tick events
        # Hire 1 more — still tiny relative to 10000
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="hire", args={"count": 1},
        ))
        env.tick()
        events = env.publish_events()
        metric_events = [e for e in events if e.type == "metric_change"]
        assert len(metric_events) == 0


class TestObservations:
    def test_observations_include_metrics(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=500.0)
        env.tick()
        obs = env.get_observations(agent)
        assert "employment_rate" in obs.content

    def test_observations_include_active_policies(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("gov")
        env.register_agent(agent, role="government", balance=10000.0)
        env.execute_action(agent, Action(
            agent_id="gov", environment="economic",
            action_type="apply_policy",
            args={"policy_name": "stimulus", "description": "Economic stimulus package"},
        ))
        obs = env.get_observations(agent)
        assert "stimulus" in obs.content

    def test_observations_include_scenario_variables(self):
        env = EconomicEnvironment(EconomicConfig())
        env.scenario_variables["gdp_target"] = 5000.0
        agent = _make_agent("f1")
        env.register_agent(agent, role="producer", balance=100.0)
        obs = env.get_observations(agent)
        assert "gdp_target" in obs.content

    def test_observations_include_actor_own_state(self):
        env = EconomicEnvironment(EconomicConfig())
        agent = _make_agent("f1", "MyFirm")
        env.register_agent(agent, role="producer", balance=750.0)
        env.execute_action(agent, Action(
            agent_id="f1", environment="economic",
            action_type="set_price", args={"price": 55.0},
        ))
        obs = env.get_observations(agent)
        assert "750" in obs.content or "750.0" in obs.content


class TestTools:
    def test_get_tools_returns_all_actions(self):
        env = EconomicEnvironment(EconomicConfig())
        tools = env.get_tools()
        tool_names = {t.name for t in tools}
        assert "set_price" in tool_names
        assert "hire" in tool_names
        assert "fire" in tool_names
        assert "invest" in tool_names
        assert "allocate" in tool_names
        assert "apply_policy" in tool_names
        assert "do_nothing" in tool_names

    def test_get_tools_returns_tool_objects_with_descriptions(self):
        env = EconomicEnvironment(EconomicConfig())
        tools = env.get_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.name
