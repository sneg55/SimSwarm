"""Tests for generate_report_task — happy path and refund behavior."""
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
         patch("saas.jobs.tasks_report._save_report_result") as save, \
         patch("saas.jobs.tasks_report.put_report_md") as putmd, \
         patch("saas.jobs.tasks_report._load_credits_charged", return_value=30):
        out = generate_report_task.run(job_id=123, user_id="u1")

    assert out["status"] == "completed"
    save.assert_called_once()
    putmd.assert_called_once_with(123, result.report_markdown)


def test_permanent_failure_marks_failed_and_refunds():
    from saas.adapters.anthropic_client import AnthropicPermanentError

    with patch("saas.jobs.tasks_report._build_runner",
               return_value=_DummyRunner(exc=AnthropicPermanentError("bad key"))), \
         patch("saas.jobs.tasks_report._mark_job_failed") as mk_failed, \
         patch("saas.jobs.tasks_report._refund_credits") as refund, \
         patch("saas.jobs.tasks_report._load_credits_charged", return_value=30):
        with pytest.raises(AnthropicPermanentError):
            generate_report_task.run(job_id=123, user_id="u1")

    mk_failed.assert_called_once()
    refund.assert_called_once_with(job_id=123, user_id="u1", credits=30)
