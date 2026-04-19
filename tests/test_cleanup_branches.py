"""Coverage for saas.jobs.cleanup additional branches."""
from unittest.mock import MagicMock, patch

import pytest

from saas.jobs.cleanup import _pod_age_seconds, _get_active_job_pod_ids, cleanup_orphaned_pods


def test_pod_age_uptime_zero_uses_last_status():
    pod = {
        "runtime": {"uptimeInSeconds": 0},
        "lastStatusChange": "Rented by User: Sun Mar 29 2020 18:34:45 GMT+0000",
    }
    # Large uptime since 2020
    assert _pod_age_seconds(pod) > 1000


def test_pod_age_returns_uptime():
    pod = {"runtime": {"uptimeInSeconds": 120}}
    assert _pod_age_seconds(pod) == 120


def test_pod_age_no_runtime_or_status():
    assert _pod_age_seconds({}) == 0


def test_pod_age_malformed_timestamp():
    pod = {"runtime": None, "lastStatusChange": "Some invalid: noisy text"}
    assert _pod_age_seconds(pod) == 0


def test_active_pod_ids_no_db_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert _get_active_job_pod_ids() is None


def test_active_pod_ids_db_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    with patch("sqlalchemy.create_engine", side_effect=RuntimeError("boom")):
        assert _get_active_job_pod_ids() is None


def test_active_pod_ids_success(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    fake_engine = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = MagicMock(
        execute=MagicMock(return_value=[("p1",), ("p2",)])
    )
    ctx.__exit__.return_value = False
    fake_engine.connect.return_value = ctx
    fake_engine.dispose = MagicMock()

    with patch("sqlalchemy.create_engine", return_value=fake_engine):
        assert _get_active_job_pod_ids() == {"p1", "p2"}


def test_cleanup_no_pods():
    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = []
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x"}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    assert result == {"active_pods": 0, "terminated": 0}


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_non_sim_pods(mock_ids):
    mock_ids.return_value = set()
    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "other-pod", "name": "not-my-pod", "runtime": {"uptimeInSeconds": 9999}},
    ]
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            cleanup_orphaned_pods()
    mock_runpod.terminate_pod.assert_not_called()


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_skips_active(mock_ids):
    mock_ids.return_value = {"active-pod"}
    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "active-pod", "name": "simswarm-sim", "runtime": {"uptimeInSeconds": 9999}},
    ]
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    mock_runpod.terminate_pod.assert_not_called()
    assert result["terminated"] == 0


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_terminate_failure_swallowed(mock_ids):
    mock_ids.return_value = set()
    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "orphan", "name": "fishcloud-sim",
         "runtime": {"uptimeInSeconds": 9999},
         "machine": {"gpuDisplayName": "L40S"}},
    ]
    mock_runpod.terminate_pod.side_effect = RuntimeError("API fail")
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    # Terminated list stays empty on failure
    assert "orphan" not in result["pod_ids"]


def test_cleanup_runpod_not_installed():
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x"}):
        with patch.dict("sys.modules", {"runpod": None}):
            with pytest.raises(RuntimeError, match="runpod package"):
                cleanup_orphaned_pods()


# ---------------------------------------------------------------------------
# Job-tag defense-in-depth (2026-04-19 task-redelivery hardening PR 2)
# ---------------------------------------------------------------------------

def test_extract_job_tag_parses_tagged_name():
    from saas.jobs.cleanup import _extract_job_tag
    assert _extract_job_tag({"name": "fishcloud-sim-j119"}) == 119


def test_extract_job_tag_parses_simswarm_prefix():
    from saas.jobs.cleanup import _extract_job_tag
    assert _extract_job_tag({"name": "simswarm-sim-j42"}) == 42


def test_extract_job_tag_untagged_legacy_name():
    from saas.jobs.cleanup import _extract_job_tag
    assert _extract_job_tag({"name": "fishcloud-sim"}) is None
    assert _extract_job_tag({"name": "simswarm-sim"}) is None


def test_extract_job_tag_garbage_name():
    from saas.jobs.cleanup import _extract_job_tag
    assert _extract_job_tag({"name": ""}) is None
    assert _extract_job_tag({"name": "fishcloud-sim-jABC"}) is None
    assert _extract_job_tag({}) is None


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
@patch("saas.jobs.persistence._get_job_status")
def test_cleanup_skips_pod_tagged_to_live_job(mock_status, mock_ids):
    """Pod whose name tag references a still-live job must NOT be terminated,
    even if the DB's simulation_jobs.pod_id no longer points at this pod."""
    mock_ids.return_value = set()  # DB pod_id has drifted; this pod is "orphan"
    mock_status.return_value = "RUNNING"

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "live-pod", "name": "fishcloud-sim-j119",
         "runtime": {"uptimeInSeconds": 9999},
         "machine": {"gpuDisplayName": "L40S"}},
    ]
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    mock_runpod.terminate_pod.assert_not_called()
    assert result["terminated"] == 0
    mock_status.assert_called_once_with(119)


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
@patch("saas.jobs.persistence._get_job_status")
def test_cleanup_terminates_pod_tagged_to_completed_job(mock_status, mock_ids):
    """Pod tagged with a job that's already COMPLETED is genuinely orphan."""
    mock_ids.return_value = set()
    mock_status.return_value = "COMPLETED"

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "done-pod", "name": "fishcloud-sim-j200",
         "runtime": {"uptimeInSeconds": 9999},
         "machine": {"gpuDisplayName": "L40S"}},
    ]
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    mock_runpod.terminate_pod.assert_called_once_with("done-pod")
    assert result["terminated"] == 1


@patch("saas.jobs.cleanup._get_active_job_pod_ids")
def test_cleanup_untagged_legacy_pod_still_terminates(mock_ids):
    """Legacy pods without a job-tag follow the old name+active-jobs path."""
    mock_ids.return_value = set()

    mock_runpod = MagicMock()
    mock_runpod.get_pods.return_value = [
        {"id": "legacy-orphan", "name": "fishcloud-sim",
         "runtime": {"uptimeInSeconds": 9999},
         "machine": {"gpuDisplayName": "L40S"}},
    ]
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "x", "ALERT_WEBHOOK_URL": ""}):
        with patch.dict("sys.modules", {"runpod": mock_runpod}):
            result = cleanup_orphaned_pods()
    mock_runpod.terminate_pod.assert_called_once_with("legacy-orphan")
    assert result["terminated"] == 1
