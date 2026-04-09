"""Test that core engine types are well-formed and serializable."""
from __future__ import annotations

import json

from simswarm.types import (
    Action,
    ActionResult,
    Agent,
    AgentActivityConfig,
    BeliefState,
    EngineConfig,
    EnvironmentConfig,
    Event,
    Observation,
    RoundSnapshot,
    ScheduledEvent,
    SimulationConfig,
    SimulationResult,
    SimulationState,
)


class TestAgentConstruction:
    def test_minimal_agent(self):
        agent = Agent(
            id="agent-1",
            name="Alice",
            persona="You are Alice, a financial analyst.",
            environments=["social"],
            belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        assert agent.id == "agent-1"
        assert agent.environments == ["social"]

    def test_belief_state_defaults(self):
        bs = BeliefState()
        assert bs.positions == {}
        assert bs.confidence == {}
        assert bs.trust == {}
        assert len(bs.exposure_history) == 0


class TestSimulationConfig:
    def test_minimal_config(self):
        config = SimulationConfig(
            seed_text="Test seed",
            goal="Predict outcomes",
            entities=[],
            environments=[],
            rounds=10,
            concurrency=4,
        )
        assert config.rounds == 10
        assert config.variables == {}
        assert config.scheduled_events == []

    def test_config_with_variables(self):
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[],
            environments=[],
            rounds=10,
            concurrency=4,
            variables={"policy": "equity_heavy", "fund_size": 2_000_000_000},
        )
        assert config.variables["policy"] == "equity_heavy"


class TestScheduledEvent:
    def test_event_construction(self):
        event = ScheduledEvent(
            round=10,
            type="policy_change",
            data={"action": "distribute", "amount": "50B"},
        )
        assert event.round == 10


class TestEngineConfig:
    def test_defaults(self):
        cfg = EngineConfig()
        assert cfg.flush_interval == 10
        assert cfg.checkpoint_interval == 50
        assert cfg.max_memory_rounds == 20
        assert cfg.concurrency == 32


class TestSimulationState:
    def test_initial_state(self):
        state = SimulationState(round=0, agents={}, environments={}, events=[], snapshots=[])
        assert state.round == 0
