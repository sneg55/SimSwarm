"""Integration test: run a full simulation with mocked LLM, verify output contracts."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from simswarm.engine import Engine
from simswarm.llm import LLMClient, LLMResponse
from simswarm.sweep import ScenarioSweep
from simswarm.types import (
    EngineConfig,
    Entity,
    EnvironmentConfig,
    SimulationConfig,
)
from tests.contracts.schemas import ChatLogEntry


def _rotating_responses():
    """Return different tool calls across rounds to simulate realistic behavior."""
    responses = [
        LLMResponse(content="", tool_calls=[
            {"name": "create_post", "args": {"text": "The market looks bearish today."}},
        ], raw={}),
        LLMResponse(content="", tool_calls=[
            {"name": "create_post", "args": {"text": "I disagree, fundamentals are strong."}},
        ], raw={}),
        LLMResponse(content="", tool_calls=[
            {"name": "do_nothing", "args": {}},
        ], raw={}),
    ]
    idx = 0
    while True:
        yield responses[idx % len(responses)]
        idx += 1


class TestFullSimulation:
    @pytest.mark.asyncio
    async def test_small_sim_produces_valid_output(self):
        response_gen = _rotating_responses()
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.side_effect = lambda *a, **kw: next(response_gen)

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Global trade tensions escalate as new tariffs are announced.",
            goal="Predict market sentiment over the next 7 days",
            entities=[
                Entity(id="e1", name="TraderBot", type="analyst", summary="Quantitative trader"),
                Entity(id="e2", name="PolicyWatcher", type="journalist", summary="Economics reporter"),
                Entity(id="e3", name="MarketMaker", type="institution", summary="Investment bank desk"),
            ],
            environments=[EnvironmentConfig(type="social", params={})],
            rounds=5,
            concurrency=4,
        )
        result = await engine.run(config)

        # Chat log should have entries
        assert len(result.chat_log) > 0

        # Every entry should validate against contract schema
        # agent_id is a str (e.g. "e1") — ChatLogEntry.agent_id is str.
        for entry in result.chat_log:
            ChatLogEntry.model_validate({
                "round_num": entry.round_num,
                "agent_id": entry.agent_id,
                "agent_name": entry.agent_name,
                "action_type": entry.action_type,
                "platform": entry.platform,
                "action_args": entry.action_args,
            })

        # Should have entries from multiple agents
        agent_names = {e.agent_name for e in result.chat_log}
        assert len(agent_names) >= 2

        # Should have entries across multiple rounds
        rounds = {e.round_num for e in result.chat_log}
        assert len(rounds) == 5

    @pytest.mark.asyncio
    async def test_sweep_produces_comparable_results(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="", tool_calls=[{"name": "do_nothing", "args": {}}], raw={},
        )

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[Entity(id="e1", name="A", type="person", summary="Test")],
            environments=[EnvironmentConfig(type="social", params={})],
            rounds=2,
            concurrency=4,
            variables={"policy": "default"},
        )
        sweep = ScenarioSweep(
            base_config=config,
            vary={"policy": ["a", "b", "c"]},
        )
        results = await engine.run_sweep(sweep)
        assert len(results) == 3
        for key, result in results:
            assert "policy" in key
            assert len(result.chat_log) > 0


class TestMultiEnvironmentSimulation:
    @pytest.mark.asyncio
    async def test_social_and_market_together(self):
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="",
            tool_calls=[{"name": "create_post", "args": {"text": "Testing"}}],
            raw={},
        )

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = SimulationConfig(
            seed_text="Test",
            goal="Test",
            entities=[Entity(id="e1", name="A", type="trader", summary="Trader")],
            environments=[
                EnvironmentConfig(type="social", params={}),
                EnvironmentConfig(type="market", params={
                    "markets": [{"question": "Will X?", "initial_price_yes": 0.5}],
                    "initial_balance": 1000.0,
                }),
            ],
            rounds=2,
            concurrency=4,
        )
        result = await engine.run(config)
        assert len(result.chat_log) > 0
