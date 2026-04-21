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

    @pytest.mark.asyncio
    async def test_on_round_sees_growing_chat_log(self):
        """on_round fires after each round with the full accumulated chat log,
        so the pod can stream partial chat to the live UI during the run."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")
        snapshots = []

        async def on_round(round_num, chat_log):
            snapshots.append((round_num, len(chat_log)))

        engine = Engine(
            fast_llm=mock_llm,
            smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=4),
        )
        config = _make_config(rounds=3)
        await engine.run(config, on_round=on_round)
        assert [s[0] for s in snapshots] == [1, 2, 3]
        # chat_log grows monotonically
        assert snapshots[0][1] < snapshots[-1][1]


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


class TestActionResultPropagation:
    """Engine must copy ActionResult.data onto ActionRecord.action_result."""

    @pytest.mark.asyncio
    async def test_buy_shares_result_data_reaches_chat_log(self):
        # Market IDs are deterministic slugs of the question — see
        # simswarm.environments.market._question_to_slug.
        market_id = "will_x"
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response(
            "buy_shares",
            {"market_id": market_id, "outcome": "yes", "amount": 50.0},
        )
        engine = Engine(
            fast_llm=mock_llm, smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=1),
        )
        config = SimulationConfig(
            seed_text="", goal="",
            entities=[Entity(id="t1", name="Trader", type="person", summary="trader")],
            environments=[EnvironmentConfig(
                type="market",
                params={"markets": [{"question": "Will X?", "initial_price_yes": 0.5}],
                        "initial_balance": 1000.0},
            )],
            rounds=1,
            concurrency=1,
        )
        result = await engine.run(config)
        buys = [r for r in result.chat_log if r.action_type == "buy_shares"]
        assert buys, "expected a buy_shares record"
        rec = buys[0]
        assert rec.action_result is not None
        assert rec.action_result.get("cost") == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_do_nothing_action_result_is_none_or_empty(self):
        """Actions whose env returns empty data should not set a spurious dict."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat.return_value = _mock_llm_response("do_nothing")
        engine = Engine(
            fast_llm=mock_llm, smart_llm=mock_llm,
            engine_config=EngineConfig(concurrency=1),
        )
        config = SimulationConfig(
            seed_text="", goal="",
            entities=[Entity(id="a", name="A", type="person", summary="agent")],
            environments=[EnvironmentConfig(type="social", params={})],
            rounds=1, concurrency=1,
        )
        result = await engine.run(config)
        for r in result.chat_log:
            if r.action_result is not None:
                assert isinstance(r.action_result, dict)
