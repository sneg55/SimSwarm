"""Tests for MinIO-sourced report tools."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from saas.jobs.report_tools_minio import ReportArtifacts, ReportTools

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts" / "small_sim"


def _load_fixture() -> ReportArtifacts:
    return ReportArtifacts(
        chat_log=json.loads((FIXTURE_DIR / "chat_log.json").read_text()),
        posts=json.loads((FIXTURE_DIR / "posts.json").read_text()),
        trades=json.loads((FIXTURE_DIR / "trades.json").read_text()),
        trajectories=json.loads((FIXTURE_DIR / "agent_trajectories.json").read_text()),
    )


def test_get_top_posts_respects_limit():
    tools = ReportTools(_load_fixture())
    out = tools.get_top_posts(limit=3)
    assert len(out) <= 3


def test_get_agent_summary_returns_expected_shape_for_known_agent():
    arts = _load_fixture()
    tools = ReportTools(arts)
    if not arts.chat_log:
        pytest.skip("fixture chat_log is empty")
    agent_id = arts.chat_log[0]["agent_id"]

    summary = tools.get_agent_summary(agent_id)
    assert set(summary.keys()) == {
        "name", "total_actions", "total_posts", "rounds_active", "sample_posts"
    }
    assert summary["total_actions"] >= 1


def test_get_agent_summary_unknown_agent_returns_zeroes():
    tools = ReportTools(_load_fixture())
    summary = tools.get_agent_summary("does-not-exist")
    assert summary["total_actions"] == 0
    assert summary["total_posts"] == 0
    assert summary["sample_posts"] == []


def test_dispatch_returns_json_string():
    tools = ReportTools(_load_fixture())
    out = tools.dispatch("get_top_posts", {"limit": 2})
    parsed = json.loads(out)
    assert isinstance(parsed, list)


def test_dispatch_unknown_tool_returns_error_json():
    tools = ReportTools(_load_fixture())
    out = tools.dispatch("nope", {})
    assert "Unknown tool" in out


def test_tool_schemas_match_original_shape():
    from simswarm.report_tools import ReportTools as RefTools
    ours = {t["function"]["name"] for t in ReportTools.tool_schemas()}
    theirs = {t["function"]["name"] for t in RefTools.tool_schemas()}
    assert ours == theirs
