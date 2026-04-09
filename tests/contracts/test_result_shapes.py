"""Contract tests: validate that engine output matches expected schemas.

These tests run against build_structured_results() which is pure Python.
The schemas defined here are the contract between SaaS and engine —
any engine (MiroShark or SimSwarm) must produce conforming output.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from tests.contracts.schemas import (
    ChatLogEntry,
    Coalition,
    Finding,
    GraphData,
    SentimentEntry,
    StructuredResults,
)

DOCKER_DIR = Path(__file__).resolve().parent.parent.parent / "infra" / "docker"


@pytest.fixture(scope="module")
def build_fn():
    """Import build_structured_results without triggering engine imports."""
    constants_path = DOCKER_DIR / "constants.py"
    results_path = DOCKER_DIR / "results.py"

    spec = importlib.util.spec_from_file_location("constants", constants_path)
    constants_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants_mod)
    sys.modules.setdefault("constants", constants_mod)

    source = results_path.read_text()
    ns = {"__builtins__": __builtins__}
    exec(compile(source, str(results_path), "exec"), ns)
    return ns["build_structured_results"]


SAMPLE_OUTLINE = {
    "summary": "Global markets face uncertainty amid trade tensions.",
    "sections": [
        {"title": "Tariff Escalation"},
        {"title": "Supply Chain Disruption"},
        {"title": "Investor Sentiment"},
    ],
}

SAMPLE_SECTIONS = {
    "Tariff Escalation": "New tariffs imposed on semiconductor imports are reshaping global trade flows. "
    "Major economies are retaliating with counter-tariffs.",
    "Supply Chain Disruption": "Manufacturing hubs in Southeast Asia report delays. "
    "Companies are diversifying supplier networks.",
    "Investor Sentiment": "Markets are pricing in a 60% probability of recession. "
    "Bond yields have inverted across major economies.",
}

SAMPLE_CHAT_LOG = [
    {
        "agent_name": "TraderBot",
        "agent_id": 1,
        "platform": "twitter",
        "action_type": "CREATE_POST",
        "action_args": {"content": "Markets looking bearish"},
        "round_num": 1,
    },
    {
        "agent_name": "Analyst",
        "agent_id": 2,
        "platform": "reddit",
        "action_type": "CREATE_COMMENT",
        "action_args": {"content": "Supply chains are resilient"},
        "round_num": 3,
    },
    {
        "agent_name": "TraderBot",
        "agent_id": 1,
        "platform": "twitter",
        "action_type": "LIKE_POST",
        "action_args": {},
        "round_num": 5,
    },
]

SAMPLE_GRAPH_DATA = {
    "nodes": [
        {"uuid": "n1", "name": "US Economy", "labels": ["Entity", "Economy"], "summary": "Largest economy"},
        {"uuid": "n2", "name": "China Trade", "labels": ["Entity", "Trade"], "summary": "Trade partner"},
    ],
    "edges": [
        {"uuid": "e1", "source_node_uuid": "n1", "target_node_uuid": "n2", "name": "trades_with"},
    ],
    "metadata": {"entity_types": ["Economy", "Trade"], "total_nodes": 2, "total_edges": 1},
}


class TestStructuredResultsContract:
    """Verify build_structured_results output conforms to StructuredResults schema."""

    def test_output_validates_against_schema(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        validated = StructuredResults.model_validate(result)
        assert validated.brief == SAMPLE_OUTLINE["summary"]

    def test_findings_match_section_count(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        validated = StructuredResults.model_validate(result)
        assert len(validated.findings) == len(SAMPLE_OUTLINE["sections"])

    def test_each_finding_has_valid_color(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for finding in result["findings"]:
            Finding.model_validate(finding)

    def test_sentiment_entries_have_valid_direction(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for entry in result["sentiment"]:
            validated = SentimentEntry.model_validate(entry)
            assert 0 <= validated.value <= 100

    def test_confidence_entries_present(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        labels = {c["label"] for c in result["confidence"]}
        assert "Agents" in labels
        assert "Rounds" in labels
        assert "Graph Entities" in labels

    def test_coalitions_validate(self, build_fn):
        result = build_fn(SAMPLE_OUTLINE, SAMPLE_SECTIONS, SAMPLE_CHAT_LOG, SAMPLE_GRAPH_DATA)
        for c in result["coalitions"]:
            validated = Coalition.model_validate(c)
            assert validated.strength >= 0
            assert validated.agents >= 0


class TestChatLogEntryContract:
    """Verify chat log entries conform to ChatLogEntry schema."""

    def test_sample_entries_validate(self):
        for entry in SAMPLE_CHAT_LOG:
            ChatLogEntry.model_validate(entry)

    def test_required_fields_present(self):
        entry = ChatLogEntry.model_validate(SAMPLE_CHAT_LOG[0])
        assert entry.agent_name == "TraderBot"
        assert entry.platform == "twitter"
        assert entry.action_type == "CREATE_POST"
        assert entry.round_num == 1


class TestGraphDataContract:
    """Verify graph data conforms to GraphData schema."""

    def test_graph_data_validates(self):
        validated = GraphData.model_validate(SAMPLE_GRAPH_DATA)
        assert validated.metadata.total_nodes == 2
        assert validated.metadata.total_edges == 1

    def test_edges_reference_existing_nodes(self):
        validated = GraphData.model_validate(SAMPLE_GRAPH_DATA)
        node_ids = {n.uuid for n in validated.nodes}
        for edge in validated.edges:
            assert edge.source_node_uuid in node_ids
            assert edge.target_node_uuid in node_ids
