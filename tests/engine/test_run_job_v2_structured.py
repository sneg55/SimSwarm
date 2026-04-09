"""Tests for run_job_v2: structured_results.json and _fallback_entities.

Covers:
  - structured_results.json validates against StructuredResults contract schema
  - brief comes from the Report object
  - findings count and accentColor validity
  - confidence labels
  - _fallback_entities() entity extraction
"""
from __future__ import annotations

import json


from tests.engine.run_job_v2_fixtures import (
    make_report,
    make_simulation_result,
    rjv2,  # noqa: F401
)


class TestStructuredResultsJson:
    def test_parses_as_dict(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_validates_against_contract_schema(self, rjv2, tmp_path):  # noqa: F811
        from tests.contracts.schemas import StructuredResults

        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        validated = StructuredResults.model_validate(data)
        assert isinstance(validated.brief, str)
        assert isinstance(validated.findings, list)

    def test_brief_matches_report(self, rjv2, tmp_path):  # noqa: F811
        report = make_report()
        rjv2.write_results(make_simulation_result(), report, str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        assert data["brief"] == report.executive_brief

    def test_findings_count_matches_report(self, rjv2, tmp_path):  # noqa: F811
        report = make_report()
        rjv2.write_results(make_simulation_result(), report, str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        assert len(data["findings"]) == len(report.findings)

    def test_findings_have_valid_accent_color(self, rjv2, tmp_path):  # noqa: F811
        from tests.contracts.schemas import Finding

        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        for finding in data["findings"]:
            f = Finding.model_validate(finding)
            assert f.accentColor.startswith("#")

    def test_confidence_has_required_labels(self, rjv2, tmp_path):  # noqa: F811
        rjv2.write_results(make_simulation_result(), make_report(), str(tmp_path))
        data = json.loads((tmp_path / "structured_results.json").read_text(encoding="utf-8"))
        labels = {c["label"] for c in data["confidence"]}
        assert "Agents" in labels
        assert "Rounds" in labels
        assert "Graph Entities" in labels


class TestFallbackEntities:
    def test_returns_requested_count(self, rjv2):  # noqa: F811
        seed = "Alice and Bob went to Paris to meet Charlie at the Eiffel Tower."
        entities = rjv2._fallback_entities(seed, count=3)
        assert len(entities) == 3

    def test_returns_entity_objects(self, rjv2):  # noqa: F811
        from simswarm.types import Entity

        seed = "Alice and Bob and Charlie attended the Summit in Geneva."
        entities = rjv2._fallback_entities(seed, count=2)
        for e in entities:
            assert isinstance(e, Entity)
            assert e.id
            assert e.name

    def test_names_start_with_uppercase(self, rjv2):  # noqa: F811
        seed = "Alice Bob Charlie Dave Eve Fred Grace Henry Iris Jack"
        entities = rjv2._fallback_entities(seed, count=5)
        for e in entities:
            assert e.name[0].isupper(), f"{e.name!r} should start with uppercase"

    def test_handles_fewer_words_than_count(self, rjv2):  # noqa: F811
        seed = "Just Alice here."
        entities = rjv2._fallback_entities(seed, count=10)
        assert isinstance(entities, list)
        assert len(entities) >= 1
