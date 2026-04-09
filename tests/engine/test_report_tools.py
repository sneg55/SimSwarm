"""Tests for ReportTools: get_top_posts, get_coalitions, get_agent_summary,
get_trajectory, dispatch, and tool_schemas."""
from __future__ import annotations

import json

import pytest

from simswarm.report import ReportTools
from tests.engine.report_fixtures import make_result


class TestReportToolsGetTopPosts:
    def test_returns_posts(self):
        tools = ReportTools(make_result())
        posts = tools.get_top_posts()
        assert isinstance(posts, list)
        assert len(posts) > 0

    def test_returns_post_dicts_with_content(self):
        tools = ReportTools(make_result())
        for post in tools.get_top_posts():
            assert "content" in post
            assert "agent_name" in post

    def test_limit_respected(self):
        tools = ReportTools(make_result())
        assert len(tools.get_top_posts(limit=1)) <= 1

    def test_default_limit_is_10(self):
        tools = ReportTools(make_result())
        assert len(tools.get_top_posts()) <= 10


class TestReportToolsGetCoalitions:
    def test_returns_list(self):
        tools = ReportTools(make_result())
        assert isinstance(tools.get_coalitions(), list)

    def test_detects_mutual_follow_coalition(self):
        tools = ReportTools(make_result())
        # Alice and Bob mutually follow each other in the fixture
        assert len(tools.get_coalitions()) >= 1

    def test_each_coalition_has_name(self):
        tools = ReportTools(make_result())
        for c in tools.get_coalitions():
            assert "name" in c


class TestReportToolsGetAgentSummary:
    def test_returns_dict_with_name_and_total_actions(self):
        tools = ReportTools(make_result())
        summary = tools.get_agent_summary("agent-alpha")
        assert isinstance(summary, dict)
        assert "name" in summary
        assert "total_actions" in summary

    def test_name_matches_agent(self):
        tools = ReportTools(make_result())
        assert tools.get_agent_summary("agent-alpha")["name"] == "Alice"

    def test_total_actions_counted(self):
        tools = ReportTools(make_result())
        assert tools.get_agent_summary("agent-alpha")["total_actions"] >= 1

    def test_unknown_agent_uses_agent_id_as_name(self):
        tools = ReportTools(make_result())
        summary = tools.get_agent_summary("nonexistent-agent")
        assert summary["name"] == "nonexistent-agent"

    def test_includes_total_posts(self):
        tools = ReportTools(make_result())
        assert "total_posts" in tools.get_agent_summary("agent-alpha")

    def test_includes_rounds_active(self):
        tools = ReportTools(make_result())
        assert "rounds_active" in tools.get_agent_summary("agent-alpha")

    def test_includes_sample_posts(self):
        tools = ReportTools(make_result())
        assert "sample_posts" in tools.get_agent_summary("agent-alpha")


class TestReportToolsGetTrajectory:
    def test_returns_per_round_trajectory(self):
        tools = ReportTools(make_result())
        assert isinstance(tools.get_trajectory("agent-alpha"), list)

    def test_trajectory_has_round_field(self):
        tools = ReportTools(make_result())
        for entry in tools.get_trajectory("agent-alpha"):
            assert "round" in entry

    def test_unknown_agent_returns_empty(self):
        tools = ReportTools(make_result())
        assert tools.get_trajectory("no-such-agent") == []


class TestReportToolsDispatch:
    def test_dispatch_get_top_posts(self):
        tools = ReportTools(make_result())
        parsed = json.loads(tools.dispatch("get_top_posts", {"limit": 2}))
        assert isinstance(parsed, list)

    def test_dispatch_get_coalitions(self):
        tools = ReportTools(make_result())
        parsed = json.loads(tools.dispatch("get_coalitions", {}))
        assert isinstance(parsed, list)

    def test_dispatch_get_agent_summary(self):
        tools = ReportTools(make_result())
        parsed = json.loads(tools.dispatch("get_agent_summary", {"agent_id": "agent-alpha"}))
        assert "name" in parsed

    def test_dispatch_unknown_tool_returns_error(self):
        tools = ReportTools(make_result())
        parsed = json.loads(tools.dispatch("nonexistent_tool", {}))
        assert "error" in parsed


class TestReportToolsToolSchemas:
    def test_returns_list_of_schemas(self):
        schemas = ReportTools.tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

    def test_each_schema_has_type_and_function(self):
        for schema in ReportTools.tool_schemas():
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]

    def test_includes_get_top_posts_schema(self):
        names = [s["function"]["name"] for s in ReportTools.tool_schemas()]
        assert "get_top_posts" in names

    def test_includes_get_agent_summary_schema(self):
        names = [s["function"]["name"] for s in ReportTools.tool_schemas()]
        assert "get_agent_summary" in names
