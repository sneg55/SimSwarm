"""Tests for recover_stale_jobs — fail+refund stale jobs paths."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from saas.jobs import recovery
from tests._recovery_helpers import ConnCtx, mock_engine_with_rows


def _stale_row(job_id=201, credits=30, pod_id="pod-dead"):
    now = datetime.now(timezone.utc)
    return (
        job_id, "user-99", "small", credits, pod_id,
        now - timedelta(hours=2),
        now - timedelta(minutes=20),
    )


def test_recover_marks_stale_job_failed_and_refunds(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    engine, conn = mock_engine_with_rows([_stale_row()], update_rowcount=1)

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = []

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery.send_orphan_alert") as mock_alert:
        result = recovery.recover_stale_jobs()

    assert result["stale_jobs"] == 1
    assert result["recovered"] == 1
    assert result["resumed"] == 0
    assert result["details"][0]["job_id"] == 201
    assert result["details"][0]["reason"] == "pod_gone"
    mock_alert.assert_called_once()
    conn.commit.assert_called()


def test_recover_terminates_orphan_pod_when_alive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    engine, _ = mock_engine_with_rows([_stale_row(job_id=202, pod_id="pod-live")],
                                      update_rowcount=1)

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-live"}]

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery.send_orphan_alert"):
        result = recovery.recover_stale_jobs()

    assert result["recovered"] == 1
    fake_runpod.terminate_pod.assert_called_once_with("pod-live")


def test_recover_terminate_failure_swallowed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("RUNPOD_API_KEY", "rk-test")

    engine, _ = mock_engine_with_rows([_stale_row(job_id=203, pod_id="pod-live2")],
                                      update_rowcount=1)

    fake_runpod = MagicMock()
    fake_runpod.get_pods.return_value = [{"id": "pod-live2"}]
    fake_runpod.terminate_pod.side_effect = RuntimeError("nope")

    with patch.dict("sys.modules", {"runpod": fake_runpod}), \
         patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery.send_orphan_alert"):
        result = recovery.recover_stale_jobs()

    assert result["recovered"] == 1


def test_recover_no_credits_no_refund_attempt(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    engine, conn = mock_engine_with_rows(
        [_stale_row(job_id=204, credits=0, pod_id=None)], update_rowcount=1,
    )

    with patch("sqlalchemy.create_engine", return_value=engine), \
         patch("saas.jobs.recovery.send_orphan_alert"):
        result = recovery.recover_stale_jobs()

    assert result["recovered"] == 1
    insert_calls = [
        c for c in conn.execute.call_args_list
        if "INSERT INTO credit_entries" in str(c.args[0])
    ]
    assert insert_calls == []


def test_recover_refund_idempotent_skip(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    row = _stale_row(job_id=205, pod_id=None)
    mock_conn = MagicMock()

    def execute_side(stmt, params=None):
        sql = str(stmt)
        if "SELECT id, user_id, tier" in sql:
            return iter([row])
        if "INSERT INTO credit_entries" in sql:
            return MagicMock(rowcount=0)
        return MagicMock(rowcount=1)

    mock_conn.execute.side_effect = execute_side

    mock_engine = MagicMock()
    mock_engine.connect.side_effect = [ConnCtx(mock_conn), ConnCtx(mock_conn)]

    with patch("sqlalchemy.create_engine", return_value=mock_engine), \
         patch("saas.jobs.recovery.send_orphan_alert"):
        result = recovery.recover_stale_jobs()

    assert result["recovered"] == 1


def test_recover_db_failure_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    engine = MagicMock()
    engine.connect.side_effect = RuntimeError("db gone")

    with patch("sqlalchemy.create_engine", return_value=engine):
        with pytest.raises(RuntimeError, match="failed to recover"):
            recovery.recover_stale_jobs()
