"""Tests for run_job_v2: structured_results.json and _fallback_entities.

structured_results.json is no longer written by the pod — it is produced by
the external-LLM Celery task (saas/jobs/tasks_report.py).  The tests here
verify that the pod does NOT produce it, and that _fallback_entities() still
works correctly for entity bootstrapping.
"""
from __future__ import annotations

import json


from tests.engine.run_job_v2_fixtures import (
    make_simulation_result,
    rjv2,  # noqa: F401
)


class TestStructuredResultsNotWrittenByPod:
    def test_structured_results_absent(self, rjv2, tmp_path):  # noqa: F811
        """structured_results.json must NOT be written by the pod."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        assert not (tmp_path / "structured_results.json").exists(), (
            "structured_results.json should be produced by Celery worker, not the pod"
        )

    def test_summary_has_report_pending(self, rjv2, tmp_path):  # noqa: F811
        """summary.json should flag report_pending=True so Celery knows to proceed."""
        rjv2.write_results(make_simulation_result(), str(tmp_path))
        data = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert data.get("report_pending") is True


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
