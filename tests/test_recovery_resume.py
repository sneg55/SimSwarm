"""Tests for recover_stale_jobs — idle pod resume paths."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from saas.jobs import recovery
from tests._recovery_helpers import mock_engine_with_rows


def test_recover_no_stale_jobs_short_circuits(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    engine, _ = mock_engine_with_rows([])

    with patch("sqlalchemy.create_engine", return_value=engine):
        result = recovery.recover_stale_jobs()

    # reporting_requeued key was added when REPORTING recovery was introduced
    assert result["stale_jobs"] == 0
    assert result["recovered"] == 0
    assert result["reporting_requeued"] == 0


def test_recover_runpod_check_fails_still_runs(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    engine, _ = mock_engine_with_rows([])
    fake_runpod = MagicMock()
    fake_runpod.get_pods.side_effect = RuntimeError("runpod down")

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine):
        result = recovery.recover_stale_jobs()

    assert result["stale_jobs"] == 0


def test_recover_resumes_idle_pod(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    now = datetime.now(timezone.utc)
    row = (101, "user-1", "small", 30, "pod-abc",
           now - timedelta(minutes=2), now - timedelta(seconds=30))
    engine, _ = mock_engine_with_rows([row])

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-abc"}]

    mock_task = MagicMock()

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery._check_pod_status", return_value="idle"), \
         patch("saas.jobs.persistence._get_job_status", return_value="RUNNING"), \
         patch("saas.jobs.tasks.resume_simulation_task", mock_task):
        result = recovery.recover_stale_jobs()

    assert result["resumed"] == 1
    assert result["recovered"] == 0
    mock_task.delay.assert_called_once()
    kwargs = mock_task.delay.call_args.kwargs
    assert kwargs["job_id"] == 101
    assert kwargs["pod_id"] == "pod-abc"


def test_recover_skips_provisioning_job_without_heartbeat(monkeypatch):
    """Main task's wait_for_worker_health can take several minutes while vLLM
    loads. During that gap the job has no heartbeat yet and DB status is
    PROVISIONING — recover must NOT claim the pod or it races with the main
    task's submit_job (worker responds 409 'already running' and main fails)."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    now = datetime.now(timezone.utc)
    # No heartbeat yet, created 2 minutes ago (well within tier timeout)
    row = (202, "user-1", "small", 30, "pod-abc",
           now - timedelta(minutes=2), None)
    engine, _ = mock_engine_with_rows([row])

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-abc"}]

    mock_task = MagicMock()

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery._check_pod_status", return_value="idle"), \
         patch("saas.jobs.persistence._get_job_status", return_value="PROVISIONING"), \
         patch("saas.jobs.tasks.resume_simulation_task", mock_task):
        result = recovery.recover_stale_jobs()

    assert result["resumed"] == 0
    assert result["recovered"] == 0
    mock_task.delay.assert_not_called()


def test_recover_skips_already_completed_job(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    now = datetime.now(timezone.utc)
    row = (102, "u1", "small", 30, "pod-xyz",
           now - timedelta(minutes=1), now - timedelta(seconds=10))
    engine, _ = mock_engine_with_rows([row])

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-xyz"}]

    mock_task = MagicMock()
    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery._check_pod_status", return_value="running"), \
         patch("saas.jobs.persistence._get_job_status", return_value="COMPLETED"), \
         patch("saas.jobs.tasks.resume_simulation_task", mock_task):
        result = recovery.recover_stale_jobs()

    mock_task.delay.assert_not_called()
    assert result["resumed"] == 0


def test_recover_skips_unknown_pod_status(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    now = datetime.now(timezone.utc)
    row = (103, "u1", "small", 30, "pod-zzz",
           now - timedelta(minutes=1), now - timedelta(seconds=10))
    engine, _ = mock_engine_with_rows([row])

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-zzz"}]

    mock_task = MagicMock()
    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery._check_pod_status", return_value="unreachable"), \
         patch("saas.jobs.tasks.resume_simulation_task", mock_task):
        result = recovery.recover_stale_jobs()

    mock_task.delay.assert_not_called()
    assert result["resumed"] == 0
