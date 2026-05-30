"""Tests for persistence_sync_idempotency helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from saas.jobs import persistence_sync_idempotency as mod


def _make_mock_engine(exec_result=None, raise_on_exec=None):
    mock_conn = MagicMock()
    if raise_on_exec:
        mock_conn.execute.side_effect = raise_on_exec
    elif exec_result is not None:
        mock_conn.execute.return_value = exec_result
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return mock_engine, mock_conn


# ---------------------------------------------------------------------------
# _load_job_snapshot
# ---------------------------------------------------------------------------

def test_load_job_snapshot_no_engine():
    with patch.object(mod, "_get_sync_engine", return_value=None):
        assert mod._load_job_snapshot(1) is None


def test_load_job_snapshot_happy_path():
    exec_result = MagicMock()
    exec_result.first.return_value = ("PROVISIONING", "pod-abc", 0)
    mock_engine, _ = _make_mock_engine(exec_result=exec_result)
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        snap = mod._load_job_snapshot(42)
    assert snap == ("PROVISIONING", "pod-abc", 0)
    mock_engine.dispose.assert_called_once()


def test_load_job_snapshot_row_missing_returns_none():
    exec_result = MagicMock()
    exec_result.first.return_value = None
    mock_engine, _ = _make_mock_engine(exec_result=exec_result)
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        assert mod._load_job_snapshot(999) is None
    mock_engine.dispose.assert_called_once()


def test_load_job_snapshot_db_error_returns_none():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("db down"))
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        assert mod._load_job_snapshot(42) is None
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _transition_to_running
# ---------------------------------------------------------------------------

def test_transition_to_running_no_engine():
    with patch.object(mod, "_get_sync_engine", return_value=None):
        mod._transition_to_running(1)  # no raise


def test_transition_to_running_happy_path():
    """A PROVISIONING row gets flipped to RUNNING."""
    result = MagicMock(rowcount=1)
    mock_engine, mock_conn = _make_mock_engine(exec_result=result)
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        mod._transition_to_running(42)
    mock_conn.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    # The UPDATE must be guarded by status='PROVISIONING'
    sql = str(mock_conn.execute.call_args.args[0])
    assert "status = 'RUNNING'" in sql
    assert "status = 'PROVISIONING'" in sql
    mock_engine.dispose.assert_called_once()


def test_transition_to_running_idempotent_on_non_provisioning():
    """Already-RUNNING (or COMPLETED/FAILED) rows produce rowcount=0 — no-op."""
    result = MagicMock(rowcount=0)
    mock_engine, _ = _make_mock_engine(exec_result=result)
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        mod._transition_to_running(42)  # no raise
    mock_engine.dispose.assert_called_once()


def test_transition_to_running_swallows_db_error():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("db down"))
    with patch.object(mod, "_get_sync_engine", return_value=mock_engine):
        mod._transition_to_running(42)  # no raise
    mock_engine.dispose.assert_called_once()
