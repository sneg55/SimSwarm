"""Tests for run_job_v2: file creation and pipeline metadata.

Covers:
  - write_results() creates all expected output files (report.md and
    structured_results.json are now produced by the Celery worker, not the pod)
  - summary.json pipeline metadata
  - posts.json / trades.json / social_graph.json shapes
  - output directory is created if missing
  - run_simulation() threads markets_config into EnvironmentConfig(type='market')
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest


from tests.engine.run_job_v2_fixtures import (
    make_simulation_result,
    rjv2,  # noqa: F401 — re-exported fixture
)

# report.md and structured_results.json are no longer written by the pod;
# they are produced by the external-LLM Celery task.
EXPECTED_FILES = {
    "chat_log.json",
    "graph_data.json",
    "posts.json",
    "top_posts.json",
    "profiles.json",
    "engagement_summary.json",
    "agent_trajectories.json",
    "social_graph.json",
    "trades.json",
    "relations.json",
    "summary.json",
}

NOT_WRITTEN_BY_POD = {"report.md", "structured_results.json"}


class TestWriteResultsCreatesFiles:
    def test_all_files_created(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        created = {p.name for p in tmp_path.iterdir()}
        missing = EXPECTED_FILES - created
        assert not missing, f"Missing output files: {missing}"

    def test_report_md_not_written_by_pod(self, rjv2, tmp_path):  # noqa: F811
        """report.md is now produced by the Celery worker, not the pod."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        created = {p.name for p in tmp_path.iterdir()}
        unexpected = NOT_WRITTEN_BY_POD & created
        assert not unexpected, f"Pod should not write: {unexpected}"

    def test_output_dir_created_if_missing(self, rjv2, tmp_path):  # noqa: F811
        nested = tmp_path / "deep" / "nested"
        assert not nested.exists()
        rjv2.write_results(make_simulation_result(), str(nested))
        assert nested.exists()
        assert (nested / "chat_log.json").exists()


class TestSummaryJson:
    def test_status_is_completed(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data["status"] == "completed"

    def test_report_pending_is_true(self, rjv2, tmp_path):  # noqa: F811
        """summary.json signals that report generation is deferred to Celery."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data.get("report_pending") is True

    def test_chat_log_entries_count(self, rjv2, tmp_path):  # noqa: F811
        result = make_simulation_result()
        rjv2.write_results(result, str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data["chat_log_entries"] == len(result.chat_log)

    def test_report_length_not_present(self, rjv2, tmp_path):  # noqa: F811
        """report_length was removed now that the pod doesn't generate the report."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert "report_length" not in data


class TestRichDataFiles:
    def test_posts_json_is_list(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "posts.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)

    def test_trades_json_contains_buy_shares(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "trades.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["side"] == "buy"

    def test_social_graph_has_edges_and_mutual_follows(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "social_graph.json").read_text(encoding="utf-8"))
        assert "edges" in data
        assert "mutual_follows" in data


class TestMarketsConfigPlumbing:
    @pytest.mark.asyncio
    async def test_run_simulation_passes_markets_to_env(self, monkeypatch):
        """run_simulation must pass markets_config into EnvironmentConfig(type='market')."""
        from infra.docker.run_job_v2_runner import run_simulation
        from simswarm.types import Entity

        captured = {}

        class FakeEngine:
            def __init__(self, **kw): pass
            async def run(self, config, on_progress=None):
                # Pull out the market env config
                market_ec = next(ec for ec in config.environments if ec.type == "market")
                captured["market_params"] = market_ec.params
                class Result:
                    chat_log = []
                    graph_data = type("G", (), {"nodes": [], "edges": [], "metadata": {}})()
                    trajectories = {}
                return Result()

        monkeypatch.setattr("infra.docker.run_job_v2_runner.Engine", FakeEngine)

        # close() is async in the real LLMClient
        fake_llm = type("X", (), {"close": AsyncMock()})()
        monkeypatch.setattr("infra.docker.run_job_v2_runner.LLMClient",
                            lambda *a, **k: fake_llm)
        monkeypatch.setattr("infra.docker.run_job_v2_runner.extract_relations",
                            AsyncMock(return_value=[]))
        monkeypatch.setattr("infra.docker.run_job_v2_runner.enrich_profiles_with_personas",
                            AsyncMock(side_effect=lambda profiles, *a, **k: profiles))

        entity = Entity(id="a", name="A", type="person", summary="x")
        markets = [{"question": "Will X?", "initial_price_yes": 0.55}]

        await run_simulation(
            seed_text="", goal="", max_rounds=1, entities=[entity], target_agents=1,
            markets_config=markets,
        )

        assert captured["market_params"]["markets"] == markets
