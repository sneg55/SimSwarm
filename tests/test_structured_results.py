"""Tests for build_structured_results and result_structured schema field."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import the function under test from infra/docker/run_job.py without
# triggering MiroFish imports (they require a GPU environment).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def run_job_module():
    """Import build_structured_results from results.py without triggering MiroFish imports."""
    docker_dir = Path(__file__).resolve().parent.parent / "infra" / "docker"
    results_path = docker_dir / "results.py"
    constants_path = docker_dir / "constants.py"
    # Build a namespace that pre-loads the constants module so results.py can
    # resolve `from constants import ...` without needing sys.path manipulation.
    import importlib.util as _ilu
    import sys as _sys

    # Load constants module into the namespace
    spec = _ilu.spec_from_file_location("constants", constants_path)
    constants_mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(constants_mod)
    _sys.modules.setdefault("constants", constants_mod)

    # Now exec results.py; it will find 'constants' via sys.modules
    source = results_path.read_text()
    ns = {"__builtins__": __builtins__}
    exec(compile(source, str(results_path), "exec"), ns)
    return ns


@pytest.fixture()
def build_fn(run_job_module):
    return run_job_module["build_structured_results"]


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

SAMPLE_OUTLINE = {
    "summary": "Climate change is accelerating across multiple fronts.",
    "sections": [
        {"title": "Rising Temperatures"},
        {"title": "Ocean Acidification"},
        {"title": "Policy Response"},
    ],
}

SAMPLE_SECTION_CONTENTS = {
    "section_01.md": "# Rising Temperatures\n\nGlobal temps have risen 1.2C.\n\nMore details here.",
    "section_02.md": "# Ocean Acidification\n\npH levels have dropped significantly.\n\nCoral reefs affected.",
    "section_03.md": "# Policy Response\n\nGovernments are enacting new laws.\n\nCarbon tax proposed.",
}

SAMPLE_CHAT_LOG = [
    {"agent_name": "Alice", "platform": "twitter", "action_type": "CREATE_POST", "action_args": {}, "round_num": 5},
    {"agent_name": "Bob", "platform": "twitter", "action_type": "LIKE_POST", "action_args": {}, "round_num": 10},
    {"agent_name": "Alice", "platform": "twitter", "action_type": "FOLLOW", "action_args": {"target": "Bob"}, "round_num": 15},
    {"agent_name": "Bob", "platform": "twitter", "action_type": "FOLLOW", "action_args": {"target": "Alice"}, "round_num": 15},
    {"agent_name": "Carol", "platform": "reddit", "action_type": "IDLE", "action_args": {}, "round_num": 20},
    {"agent_name": "Carol", "platform": "reddit", "action_type": "COMMENT", "action_args": {}, "round_num": 25},
]

SAMPLE_GRAPH_DATA = {
    "nodes": [{"uuid": "n1", "name": "Climate"}, {"uuid": "n2", "name": "Ocean"}],
    "edges": [{"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2"}],
    "metadata": {"entity_types": ["Topic"], "total_nodes": 2, "total_edges": 1},
}


# ---------------------------------------------------------------------------
# Tests — build_structured_results with sample data
# ---------------------------------------------------------------------------

class TestBuildStructuredResults:
    def test_brief_from_outline_summary(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        assert result["brief"] == "Climate change is accelerating across multiple fronts."

    def test_findings_count_matches_sections(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        assert len(result["findings"]) == 3

    def test_findings_have_correct_titles(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        titles = [f["title"] for f in result["findings"]]
        assert titles == ["Rising Temperatures", "Ocean Acidification", "Policy Response"]

    def test_findings_have_label_and_color(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for finding in result["findings"]:
            assert finding["label"] == "FINDING"
            assert finding["accentColor"].startswith("#")

    def test_findings_description_excludes_headings(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        # First finding description should be from section content, not heading
        desc = result["findings"][0]["description"]
        assert not desc.startswith("#")
        assert "1.2C" in desc

    def test_sentiment_per_platform(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        labels = {s["label"] for s in result["sentiment"]}
        assert "Twitter" in labels
        assert "Reddit" in labels

    def test_sentiment_values_are_percentages(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for s in result["sentiment"]:
            assert 0 <= s["value"] <= 100
            assert s["direction"] in ("positive", "negative")

    def test_coalitions_from_mutual_follows(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        assert len(result["coalitions"]) >= 1
        coalition = result["coalitions"][0]
        assert coalition["agents"] == 2
        assert "Alice" in coalition["description"]
        assert "Bob" in coalition["description"]

    def test_confidence_metrics(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        confidence = result["confidence"]
        assert len(confidence) == 4
        labels = {c["label"] for c in confidence}
        assert labels == {"Agents", "Rounds", "Graph Entities", "Trades"}
        # 3 agents: Alice, Bob, Carol
        agents_entry = next(c for c in confidence if c["label"] == "Agents")
        assert agents_entry["value"] == "3"
        # Graph has 2 nodes
        graph_entry = next(c for c in confidence if c["label"] == "Graph Entities")
        assert graph_entry["value"] == "2"

    def test_rounds_shows_max_round_num_not_action_count(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        rounds_entry = next(c for c in result["confidence"] if c["label"] == "Rounds")
        # max round_num is 25, not len(chat_log) which is 6
        assert rounds_entry["value"] == "25"

    def test_trades_count_in_confidence(self, build_fn):
        chat_with_trades = SAMPLE_CHAT_LOG + [
            {"agent_name": "Alice", "platform": "polymarket", "action_type": "BUY", "action_args": {}, "round_num": 12},
            {"agent_name": "Bob", "platform": "polymarket", "action_type": "SELL", "action_args": {}, "round_num": 18},
            {"agent_name": "Carol", "platform": "polymarket", "action_type": "CREATE_MARKET", "action_args": {}, "round_num": 5},
        ]
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, chat_with_trades, SAMPLE_GRAPH_DATA)
        trades_entry = next(c for c in result["confidence"] if c["label"] == "Trades")
        # Only BUY and SELL count, not CREATE_MARKET
        assert trades_entry["value"] == "2"

    def test_trades_zero_when_no_polymarket_trades(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        trades_entry = next(c for c in result["confidence"] if c["label"] == "Trades")
        assert trades_entry["value"] == "0"


# ---------------------------------------------------------------------------
# Tests — empty inputs
# ---------------------------------------------------------------------------

class TestBuildStructuredResultsEmpty:
    def test_empty_inputs_returns_empty_arrays(self, build_fn):
        result = build_fn(None, {}, [], {"metadata": {}})
        assert result["brief"] == ""
        assert result["findings"] == []
        assert result["sentiment"] == []
        assert result["coalitions"] == []
        assert len(result["confidence"]) == 4

    def test_empty_outline_no_findings(self, build_fn):
        result = build_fn({}, {}, [], {"metadata": {}})
        assert result["findings"] == []

    def test_no_actions_no_coalitions(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, [], SAMPLE_GRAPH_DATA)
        assert result["coalitions"] == []

    def test_result_is_json_serializable(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTION_CONTENTS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        # Should not raise
        json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tests — JobResponse schema includes result_structured
# ---------------------------------------------------------------------------

class TestJobResponseSchema:
    def test_result_structured_in_job_response(self):
        from saas.jobs.schemas import JobResponse
        fields = JobResponse.model_fields
        assert "result_structured" in fields

    def test_result_structured_defaults_to_none(self):
        from saas.jobs.schemas import JobResponse
        field = JobResponse.model_fields["result_structured"]
        assert field.default is None

    def test_result_structured_null_for_old_jobs(self):
        """Simulate an old job that has no result_structured — should default to None."""
        from saas.jobs.schemas import JobResponse
        job_data = {
            "id": 1,
            "user_id": "u1",
            "seed_text": "test",
            "goal": "test",
            "tier": "small",
            "credits_charged": 30,
            "status": "COMPLETED",
            "pipeline_stage": None,
            "error_message": None,
            "created_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T01:00:00Z",
        }
        resp = JobResponse(**job_data)
        assert resp.result_structured is None
