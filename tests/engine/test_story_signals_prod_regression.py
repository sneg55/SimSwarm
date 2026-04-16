"""Regression tests for simswarm.story_signals against prod fixtures.

Kept in a dedicated module so tests/engine/test_story_signals.py stays under
the 300-line budget while still gaining full coverage for prod jobs.
"""
from __future__ import annotations

import json
from pathlib import Path

from simswarm import story_signals


class TestBuildStorySignalsProdRegression:
    """Regression: job #109 — SEC AI disclosure rules, 30-day horizon.

    Today's adapter returns `coalitions=[]` (mutual-follow misses thematic alignment).
    Our new story_signals.py MUST surface at least two named coalitions for the
    industry bloc and regulator/transparency bloc that are obviously present in
    the data.
    """

    @staticmethod
    def _load_job_109():
        base = Path(__file__).resolve().parent / "fixtures"
        chat_log = json.loads((base / "job_109_chat_log.json").read_text())
        graph = json.loads((base / "job_109_graph.json").read_text())
        return chat_log, graph

    def test_surfaces_at_least_two_named_coalitions(self):
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        assert len(result["named_coalitions"]) >= 2

    def test_sim_scale_market_stress_none_observed(self):
        # Prod job 109 had 0 trades — verify we report honestly, not as confidence.
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        assert result["sim_scale"]["market_stress"] == "none_observed"

    def test_phase_boundaries_time_anchored(self):
        chat_log, graph = self._load_job_109()
        result = story_signals.build_story_signals(chat_log, graph, forecast_days=30)
        for phase in result["phase_boundaries"]:
            assert "Week" in phase["week_range"]
