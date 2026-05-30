"""Tests for generate_report_task — happy path and failure marking behavior."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from saas.jobs.tasks_report import generate_report_task


class _DummyRunner:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    async def run(self):
        if self._exc is not None:
            raise self._exc
        return self._result


@pytest.mark.asyncio
async def test_happy_path_persists_and_marks_completed():
    from saas.jobs.report import ReportResult

    result = ReportResult(
        report_markdown="## Executive Summary\nAll went well.\n",
        executive_brief="All went well.",
        findings=[{"title": "F1", "content": "X"}],
    )

    with patch("saas.jobs.tasks_report._build_runner", return_value=_DummyRunner(result=result)), \
         patch("saas.jobs.tasks_report._load_job_artifacts", return_value=("[]", "{}")), \
         patch("saas.jobs.tasks_report._save_report_result") as save, \
         patch("saas.jobs.tasks_report.put_report_md") as putmd:
        out = generate_report_task.run(job_id=123, user_id="u1")

    assert out["status"] == "completed"
    save.assert_called_once()
    saved_structured = save.call_args.kwargs["structured"]
    import json as _json
    parsed = _json.loads(saved_structured)
    # Path-3 structured shape: LLM-authored + deterministic signals
    expected_keys = {
        "brief", "verdict", "findings",
        "stakeholder_positions", "named_coalitions", "phase_boundaries",
        "quotable_posts", "disagreement_axis", "sim_scale",
    }
    assert expected_keys <= set(parsed.keys())
    putmd.assert_called_once_with(123, result.report_markdown)


def test_permanent_failure_marks_failed():
    from saas.adapters.anthropic_client import AnthropicPermanentError

    with patch("saas.jobs.tasks_report._build_runner",
               return_value=_DummyRunner(exc=AnthropicPermanentError("bad key"))), \
         patch("saas.jobs.tasks_report._mark_job_failed") as mk_failed:
        with pytest.raises(AnthropicPermanentError):
            generate_report_task.run(job_id=123, user_id="u1")

    mk_failed.assert_called_once()


def test_post_runner_exception_marks_failed():
    """If _build_structured or _save_report_result raises (e.g. corrupt artifacts),
    generate_report_task must call _finalize_as_failed and mark the job failed —
    NOT leak the exception past Celery and leave the job stuck in REPORTING."""
    from saas.jobs.report import ReportResult

    result = ReportResult(
        report_markdown="## Executive Summary\nAll went well.\n",
        executive_brief="All went well.",
        findings=[{"title": "F1", "content": "X"}],
    )

    with patch("saas.jobs.tasks_report._build_runner", return_value=_DummyRunner(result=result)), \
         patch("saas.jobs.tasks_report._load_job_artifacts",
               side_effect=RuntimeError("db down")), \
         patch("saas.jobs.tasks_report._mark_job_failed") as mk_failed:
        with pytest.raises(RuntimeError):
            generate_report_task.run(job_id=123, user_id="u1")

    mk_failed.assert_called_once()
    call = mk_failed.call_args
    assert call.kwargs.get("job_id") == 123 or (call.args and call.args[0] == 123)
    reason_arg = call.kwargs.get("error_message") or (call.args[1] if len(call.args) > 1 else "")
    assert "report_persist_failed" in reason_arg
