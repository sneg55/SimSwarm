"""Tests for saas/workers/cleanup.py."""
import pytest
from unittest.mock import patch, MagicMock

from saas.jobs.cleanup import cleanup_orphaned_pods


def test_cleanup_raises_when_no_runpod_api_key(monkeypatch):
    """cleanup_orphaned_pods must raise RuntimeError when RUNPOD_API_KEY is unset."""
    monkeypatch.setenv("RUNPOD_API_KEY", "")

    with pytest.raises(RuntimeError, match="RUNPOD_API_KEY not set"):
        cleanup_orphaned_pods()


def _make_pod(pod_id="pod-1", name="fishcloud-sim", uptime_seconds=600, gpu="L40S"):
    return {
        "id": pod_id,
        "name": name,
        "machine": {"gpuDisplayName": gpu},
        "runtime": {"uptimeInSeconds": uptime_seconds},
    }


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_young_pods(mock_get_ids):
    """Pods younger than 3 minutes should not be terminated."""
    mock_get_ids.return_value = set()

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        _make_pod(pod_id="young-pod", uptime_seconds=120),
    ]

    with patch.dict("os.environ", {"RUNPOD_API_KEY": "test-key"}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            cleanup_orphaned_pods()

    mock_runpod.terminate_pod.assert_not_called()


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_entirely_on_db_error(mock_get_ids):
    """When DB is unreachable, cleanup should skip entirely."""
    mock_get_ids.return_value = None

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        _make_pod(pod_id="pod-1", uptime_seconds=3600),
    ]

    with patch.dict("os.environ", {"RUNPOD_API_KEY": "test-key", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()

    mock_runpod.terminate_pod.assert_not_called()
    assert result.get("skipped") == "db_unreachable"


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_terminates_old_orphan(mock_get_ids):
    """Pod older than grace period with no matching job should be terminated."""
    mock_get_ids.return_value = set()

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        _make_pod(pod_id="orphan-pod", uptime_seconds=3600),
    ]

    with patch.dict("os.environ", {"RUNPOD_API_KEY": "test-key", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()

    mock_runpod.terminate_pod.assert_called_once_with("orphan-pod")
    assert "orphan-pod" in result["pod_ids"]
