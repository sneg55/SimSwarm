"""Tests for run_job_v2: file creation and pipeline metadata.

Covers:
  - write_results() creates all expected output files
  - summary.json pipeline metadata
  - posts.json / trades.json / social_graph.json shapes
  - output directory is created if missing
"""
from __future__ import annotations

import json

import pytest

from tests.engine.run_job_v2_fixtures import (
    make_report,
    make_simulation_result,
    rjv2,  # noqa: F401 — re-exported fixture
)

EXPECTED_FILES = {
    "report.md",
    "chat_log.json",
    "graph_data.json",
    "structured_results.json",
    "posts.json",
    "engagement_summary.json",
    "agent_trajectories.json",
    "social_graph.json",
    "trades.json",
    "summary.json",
}


class TestWriteResultsCreatesFiles:
    def test_all_files_created(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        created = {p.name for p in tmp_path.iterdir()}
        missing = EXPECTED_FILES - created
        assert not missing, f"Missing output files: {missing}"

    def test_report_md_contains_executive_summary(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "Executive Summary" in content

    def test_output_dir_created_if_missing(self, rjv2, tmp_path):
        nested = tmp_path / "deep" / "nested"
        assert not nested.exists()
        rjv2.write_results(make_simulation_result(), make_report(), str(nested))
        assert nested.exists()
        assert (nested / "report.md").exists()


class TestSummaryJson:
    def test_status_is_completed(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data["status"] == "completed"

    def test_chat_log_entries_count(self, rjv2, tmp_path):
        result = make_simulation_result()
        rjv2.write_results(result, make_report(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data["chat_log_entries"] == len(result.chat_log)

    def test_report_length_present(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert "report_length" in data
        assert isinstance(data["report_length"], int)


class TestRichDataFiles:
    def test_posts_json_is_list(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "posts.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)

    def test_trades_json_contains_buy_shares(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "trades.json").read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action_type"] == "buy_shares"

    def test_social_graph_has_edges_and_mutual_follows(self, rjv2, tmp_path):
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "social_graph.json").read_text(encoding="utf-8"))
        assert "edges" in data
        assert "mutual_follows" in data
