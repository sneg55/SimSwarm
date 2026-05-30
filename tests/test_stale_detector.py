"""Unit tests for the stale-job detector.

These mock DB/Temporal access to exercise the phase-budget decision logic
deterministically without standing up postgres or a temporal cluster.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from saas.jobs.stale_detector import (
    _phase_budget_s,
    _running_budget_s,
    detect_stale_jobs,
)


def test_phase_budget_returns_tier_timeout_for_running():
    # Large tier = 43200s + 600s grace
    assert _running_budget_s("large") == 43800
    assert _phase_budget_s("RUNNING", "large") == 43800
    assert _phase_budget_s("RUNNING", "small") == 3300  # 2700 + 600


def test_phase_budget_short_for_pending_and_provisioning():
    assert _phase_budget_s("PENDING", "small") == 300
    assert _phase_budget_s("PROVISIONING", "small") == 3600


def test_phase_budget_reporting_generous_for_celery_retries():
    assert _phase_budget_s("REPORTING", "small") == 4500


def _stale_job(age_seconds: int, status: str = "PROVISIONING", workflow_id: str = "sim-1"):
    return {
        "id": 1, "user_id": "u1", "status": status, "tier": "small",
        "pod_id": "pod-xyz",
        "workflow_id": workflow_id,
        "created_at": datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    }


@patch("saas.jobs.stale_detector._load_live_jobs")
def test_detector_skips_jobs_within_budget(mock_load):
    mock_load.return_value = [_stale_job(age_seconds=60, status="PROVISIONING")]
    result = detect_stale_jobs()
    assert result["reconciled"] == 0


@patch("saas.jobs.stale_detector._reconcile_stale_job")
@patch("saas.jobs.stale_detector._load_live_jobs")
def test_detector_skips_when_temporal_still_running(mock_load, mock_reconcile):
    mock_load.return_value = [_stale_job(age_seconds=7200, status="PROVISIONING")]
    with patch("saas.jobs.stale_detector.asyncio.run", return_value=False):
        result = detect_stale_jobs()
    mock_reconcile.assert_not_called()
    assert result["reconciled"] == 0


@patch("saas.jobs.stale_detector._reconcile_stale_job")
@patch("saas.jobs.stale_detector._load_live_jobs")
def test_detector_reconciles_over_budget_with_dead_temporal(
    mock_load, mock_reconcile,
):
    mock_load.return_value = [_stale_job(age_seconds=7200, status="PROVISIONING")]
    with patch("saas.jobs.stale_detector.asyncio.run", return_value=True):
        result = detect_stale_jobs()

    mock_reconcile.assert_called_once()
    assert result["reconciled"] == 1
    assert result["job_ids"] == [1]


@patch("saas.jobs.stale_detector._reconcile_stale_job")
@patch("saas.jobs.stale_detector._load_live_jobs")
def test_detector_reconciles_when_workflow_id_missing(mock_load, mock_reconcile):
    """A stale job without a workflow_id means workflow start likely failed
    before the row was committed — reconcile immediately, no Temporal check."""
    job = _stale_job(age_seconds=7200, status="PROVISIONING")
    job["workflow_id"] = None
    mock_load.return_value = [job]
    result = detect_stale_jobs()
    mock_reconcile.assert_called_once()
    assert result["reconciled"] == 1


@patch("saas.jobs.stale_detector._load_live_jobs")
def test_detector_returns_empty_on_no_jobs(mock_load):
    mock_load.return_value = []
    result = detect_stale_jobs()
    assert result == {"scanned": 0, "reconciled": 0}


@patch("saas.jobs.stale_detector._best_effort_terminate_pod")
@patch("saas.jobs.persistence._mark_job_failed_sync")
def test_reconcile_marks_failed_and_terminates_pod(
    mock_mark_failed, mock_terminate,
):
    from saas.jobs.stale_detector import _reconcile_stale_job

    job = _stale_job(age_seconds=9999, status="PROVISIONING")
    _reconcile_stale_job(job, "test reason")

    mock_mark_failed.assert_called_once()
    mock_terminate.assert_called_once_with("pod-xyz")


def test_best_effort_terminate_pod_swallows_errors():
    from saas.jobs.stale_detector import _best_effort_terminate_pod

    # Empty pod_id — no-op, no raise
    _best_effort_terminate_pod("")

    mock_runpod = MagicMock()
    mock_runpod.terminate_pod.side_effect = RuntimeError("boom")
    with patch.dict("sys.modules", {"runpod": mock_runpod}):
        _best_effort_terminate_pod("pod-xyz")  # must not raise
