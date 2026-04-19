"""Tests for finalization activities (upload_and_finalize, refund_credits)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_and_finalize_persists_results_and_enqueues_report():
    from saas.workflows.activities.finalization import upload_and_finalize

    result = {
        "pod_id": "pod-1",
        "provision_seconds": 100, "pipeline_seconds": 700,
        "report": "", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}",
        "sim_data_uploaded": True,
    }

    with patch("saas.jobs.persistence._update_job_metadata") as mock_meta, \
         patch("saas.jobs.persistence._save_job_results") as mock_save, \
         patch("saas.jobs.persistence._update_sim_data_available") as mock_sim_avail, \
         patch("saas.jobs.persistence._transition_to_reporting") as mock_reporting, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as mock_enqueue:
        await upload_and_finalize(job_id=55, user_id="u1", result=result)

    mock_meta.assert_called_once()
    mock_save.assert_called_once()
    mock_sim_avail.assert_called_once_with(55, True)
    mock_reporting.assert_called_once_with(55)
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_upload_and_finalize_raises_when_upload_missing():
    from saas.workflows.activities.finalization import upload_and_finalize

    result = {
        "pod_id": "pod-1",
        "provision_seconds": 100, "pipeline_seconds": 700,
        "sim_data_uploaded": False,
    }

    with patch("saas.jobs.persistence._update_job_metadata"), \
         patch("saas.jobs.persistence._save_job_results"), \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as mock_enqueue:
        with pytest.raises(RuntimeError, match="sim_data_upload_failed"):
            await upload_and_finalize(job_id=55, user_id="u1", result=result)

    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_refund_credits_invokes_refund_helper():
    from saas.workflows.activities.finalization import refund_credits

    with patch("saas.jobs.refund._refund_credits") as mock_refund, \
         patch("saas.jobs.persistence._mark_job_failed_sync") as mock_mark:
        await refund_credits(
            job_id=10, user_id="u", credits=90,
            error_message="activity_timed_out",
        )

    mock_mark.assert_called_once_with(10, "activity_timed_out")
    mock_refund.assert_called_once_with(job_id=10, user_id="u", credits=90)


@pytest.mark.asyncio
async def test_refund_credits_skips_refund_for_zero_credits():
    from saas.workflows.activities.finalization import refund_credits

    with patch("saas.jobs.refund._refund_credits") as mock_refund, \
         patch("saas.jobs.persistence._mark_job_failed_sync") as mock_mark:
        await refund_credits(
            job_id=11, user_id="u", credits=0, error_message="err",
        )

    mock_mark.assert_called_once()
    mock_refund.assert_not_called()
