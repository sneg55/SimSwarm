"""End-to-end integration: deriver output flows into MarketConfig."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_fake_grok(markets):
    client = MagicMock()
    client.responses.create.return_value = MagicMock(
        output_text=json.dumps({"markets": markets})
    )
    return client


class TestMarketsEndToEnd:
    @pytest.mark.asyncio
    async def test_derived_markets_reach_market_env(self, monkeypatch):
        # 1. Stub the LLM client so derive_markets runs its real validation path
        monkeypatch.setattr(
            "saas.jobs.market_derivation._build_client",
            lambda: _make_fake_grok([
                {"question": "Will it rain?", "initial_price_yes": 0.6, "rationale": "r1"},
                {"question": "Will it snow?", "initial_price_yes": 0.2, "rationale": "r2"},
            ]),
        )

        from saas.jobs.market_derivation import derive_markets
        derivation = derive_markets(goal="Weather?", enriched_seed="", tier="small")
        assert derivation["source"] == "llm"

        # 2. Prove run_simulation accepts + plumbs the list into the market env
        from infra.docker.run_job_v2_runner import run_simulation
        from simswarm.types import Entity

        captured = {}

        class FakeEngine:
            def __init__(self, **kw): pass
            async def run(self, config, on_progress=None):
                market_ec = next(ec for ec in config.environments if ec.type == "market")
                captured["market_params"] = market_ec.params
                class R:
                    chat_log = []
                    graph_data = type("G", (), {"nodes": [], "edges": [], "metadata": {}})()
                    trajectories = {}
                return R()

        monkeypatch.setattr("infra.docker.run_job_v2_runner.Engine", FakeEngine)
        monkeypatch.setattr(
            "infra.docker.run_job_v2_runner.LLMClient",
            lambda *a, **k: MagicMock(close=AsyncMock()),
        )
        monkeypatch.setattr(
            "infra.docker.run_job_v2_runner.extract_relations",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            "infra.docker.run_job_v2_runner.enrich_profiles_with_personas",
            AsyncMock(side_effect=lambda p, *a, **k: p),
        )

        await run_simulation(
            seed_text="", goal="Weather?", max_rounds=1,
            entities=[Entity(id="a", name="A", type="person", summary="x")],
            target_agents=1,
            markets_config=derivation["markets"],
        )

        assert captured["market_params"]["markets"] == [
            {"question": "Will it rain?", "initial_price_yes": 0.6},
            {"question": "Will it snow?", "initial_price_yes": 0.2},
        ]
