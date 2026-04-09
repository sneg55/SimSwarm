"""Tests for adapt_structured and module-level constants."""
from __future__ import annotations

from simswarm.adapter import (
    FINDING_COLORS,
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    adapt_chat_log,
    adapt_graph_data,
    adapt_structured,
)
from tests.contracts.schemas import Coalition, SentimentEntry, StructuredResults
from tests.engine.adapter_fixtures import BRIEF, make_findings, make_graph, make_records


def _run(brief=BRIEF, findings=None, records=None, graph=None):
    if findings is None:
        findings = make_findings()
    chat_log = adapt_chat_log(records if records is not None else make_records())
    graph_data = adapt_graph_data(graph if graph is not None else make_graph())
    return adapt_structured(brief, findings, chat_log, graph_data)


class TestAdaptStructuredSchema:
    def test_validates_against_schema(self):
        StructuredResults.model_validate(_run())

    def test_brief_matches_input(self):
        assert _run()["brief"] == BRIEF

    def test_findings_count_matches_input(self):
        assert len(_run()["findings"]) == len(make_findings())

    def test_findings_use_finding_colors(self):
        for i, f in enumerate(_run()["findings"]):
            assert f["accentColor"] == FINDING_COLORS[i % len(FINDING_COLORS)]

    def test_empty_inputs_produce_valid_output(self):
        from simswarm.types import GraphSnapshot
        empty_graph = GraphSnapshot(
            nodes=[], edges=[],
            metadata={"entity_types": [], "total_nodes": 0, "total_edges": 0},
        )
        result = adapt_structured("", [], [], adapt_graph_data(empty_graph))
        StructuredResults.model_validate(result)


class TestAdaptStructuredConfidence:
    def test_includes_agents(self):
        assert "Agents" in {c["label"] for c in _run()["confidence"]}

    def test_includes_rounds(self):
        assert "Rounds" in {c["label"] for c in _run()["confidence"]}

    def test_includes_graph_entities(self):
        assert "Graph Entities" in {c["label"] for c in _run()["confidence"]}

    def test_agents_value_counts_unique_names(self):
        entry = next(c for c in _run()["confidence"] if c["label"] == "Agents")
        assert entry["value"] == "2"  # TraderBot + Analyst

    def test_rounds_is_max_round_num(self):
        entry = next(c for c in _run()["confidence"] if c["label"] == "Rounds")
        assert entry["value"] == "4"  # max round_num in make_records

    def test_trades_counted(self):
        result = _run()
        assert "Trades" in {c["label"] for c in result["confidence"]}
        entry = next(c for c in result["confidence"] if c["label"] == "Trades")
        assert entry["value"] == "1"  # one BUY on polymarket in make_records


class TestAdaptStructuredSentiment:
    def test_sentiment_direction_valid(self):
        for entry in _run()["sentiment"]:
            validated = SentimentEntry.model_validate(entry)
            assert 0 <= validated.value <= 100


class TestAdaptStructuredCoalitions:
    def test_coalitions_validate(self):
        for c in _run()["coalitions"]:
            validated = Coalition.model_validate(c)
            assert validated.strength >= 0
            assert validated.agents >= 0


class TestAdapterConstants:
    def test_finding_colors_has_six_entries(self):
        assert len(FINDING_COLORS) == 6

    def test_positive_words_nonempty_set(self):
        assert isinstance(POSITIVE_WORDS, (set, frozenset))
        assert len(POSITIVE_WORDS) > 0

    def test_negative_words_nonempty_set(self):
        assert isinstance(NEGATIVE_WORDS, (set, frozenset))
        assert len(NEGATIVE_WORDS) > 0
