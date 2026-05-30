"""Tests for adapt_structured post-Path-3 refactor."""
from __future__ import annotations

from simswarm.adapter import adapt_chat_log, adapt_graph_data, adapt_structured
from tests.contracts.schemas import StructuredResults
from tests.engine.adapter_fixtures import BRIEF, make_findings, make_graph, make_records


def _run(brief=BRIEF, findings=None, records=None, graph=None, forecast_days=30):
    if findings is None:
        findings = make_findings()
    chat_log = adapt_chat_log(records if records is not None else make_records())
    graph_data = adapt_graph_data(graph if graph is not None else make_graph())
    return adapt_structured(
        brief=brief,
        findings=findings,
        chat_log=chat_log,
        graph_data=graph_data,
        forecast_days=forecast_days,
        verdict="Sample verdict sentence in plain English.",
    )


class TestAdaptStructuredSchema:
    def test_validates_against_schema(self):
        StructuredResults.model_validate(_run())

    def test_brief_matches_input(self):
        assert _run()["brief"] == BRIEF

    def test_verdict_matches_input(self):
        assert _run()["verdict"] == "Sample verdict sentence in plain English."

    def test_sim_scale_present(self):
        assert "sim_scale" in _run()
        assert _run()["sim_scale"]["horizon_days"] == 30

    def test_named_coalitions_present(self):
        assert "named_coalitions" in _run()

    def test_no_legacy_sentiment_key(self):
        assert "sentiment" not in _run()

    def test_no_legacy_confidence_key(self):
        assert "confidence" not in _run()

    def test_empty_inputs_produce_valid_output(self):
        from simswarm.types import GraphSnapshot
        empty_graph = GraphSnapshot(
            nodes=[], edges=[],
            metadata={"entity_types": [], "total_nodes": 0, "total_edges": 0},
        )
        result = adapt_structured(
            brief="", findings=[], chat_log=[],
            graph_data=adapt_graph_data(empty_graph),
            forecast_days=7, verdict="",
        )
        StructuredResults.model_validate(result)
