"""Test prompt template rendering."""
from __future__ import annotations

from simswarm.prompts.templates import render_agent_system, render_agent_observation
from simswarm.types import Entity, Observation


class TestAgentSystemPrompt:
    def test_includes_entity_name(self):
        entity = Entity(id="e1", name="Alice Chen", type="analyst", summary="Senior financial analyst at Goldman Sachs")
        prompt = render_agent_system(entity, goal="Predict market reaction to tariffs")
        assert "Alice Chen" in prompt
        assert "financial analyst" in prompt

    def test_includes_goal(self):
        entity = Entity(id="e1", name="X", type="person", summary="Test")
        prompt = render_agent_system(entity, goal="Analyze trade policy")
        assert "trade policy" in prompt.lower() or "Analyze" in prompt

    def test_includes_stance_when_provided(self):
        entity = Entity(id="e1", name="X", type="person", summary="Test")
        prompt = render_agent_system(entity, goal="Test", stance="supportive")
        assert "supportive" in prompt.lower()


class TestAgentObservation:
    def test_includes_observations(self):
        obs = [Observation(environment="social", content="[Alice] Markets are down")]
        result = render_agent_observation(obs, variables={"policy": "equity_heavy"})
        assert "Markets are down" in result

    def test_includes_variables(self):
        obs = [Observation(environment="social", content="Feed")]
        result = render_agent_observation(obs, variables={"fund_size": "2T"})
        assert "fund_size" in result

    def test_empty_observations(self):
        result = render_agent_observation([], variables={})
        assert isinstance(result, str)
