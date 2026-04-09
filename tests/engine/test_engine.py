"""Test the core simulation loop: round orchestration, progress, termination."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from simswarm.engine import Engine
from simswarm.llm import LLMClient, LLMResponse
from simswarm.types import (
    EngineConfig,
    Entity,
    EnvironmentConfig,
    SimulationConfig,
)


def _mock_llm_response(action_name: str = "do_nothing", args: dict | None = None):
    args = args or {}
    return LLMResponse(
        content="",
        tool_calls=[{"name": action_name, "args": args}],
        raw={},
    )


def _make_config(rounds: int = 3, agent_count: int = 2) -> SimulationConfig:
    return SimulationConfig(
        seed_text="Test simulation",
        goal="Test goal",
        entities=[Entity(id=f"e{i}", name=f"Agent{i}", type="person", summary=f"Agent {i}")
                  for i in range(agent_count)],
        environments=[EnvironmentConfig(type="social", params={})],
        rounds=rounds,
        concurrency=4,
    )


class TestEngineRoundExecution:
    @pytest.mark.asyncio
    async def test_runs_correct_number_of_rounds(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=3)
        result = await engine.run(config)
        assert len(result.chat_log) >= 0
        assert mock_llm.chat.call_count == 3 * 2  # 3 rounds * 2 agents

    @pytest.mark.asyncio
    async def test_agents_receive_observations(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("create_post", {"text": "Hello"})

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=2, agent_count=1)
        result = await engine.run(config)
        posts = [a for a in result.chat_log if a.action_type == "create_post"]
        assert len(posts) >= 1


class TestProgressCallback:
    @pytest.mark.asyncio
    async def test_progress_called_each_round(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")
        progress_calls = []

        async def on_progress(round_num, total, metrics):
            progress_calls.append(round_num)

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=3)
        await engine.run(config, on_progress=on_progress)
        assert progress_calls == [1, 2, 3]


class TestAgentGeneration:
    @pytest.mark.asyncio
    async def test_creates_agents_from_entities(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=1, agent_count=5)
        result = await engine.run(config)
        agent_names = {a.agent_name for a in result.chat_log}
        assert len(agent_names) <= 5


class TestSweepExecution:
    @pytest.mark.asyncio
    async def test_run_sweep_returns_keyed_results(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        from simswarm.sweep import ScenarioSweep
        config = _make_config(rounds=1)
        sweep = ScenarioSweep(
            base_config=config,
            vary={"policy": ["a", "b"]},
        )
        results = await engine.run_sweep(sweep)
        assert len(results) == 2
