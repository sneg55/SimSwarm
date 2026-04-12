"""Tests for saas.jobs.persistence_sync_progress — progress/metadata sync writes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from saas.jobs import persistence_sync_progress as psp


def _engine_pair(raise_on_exec=None):
    mock_conn = MagicMock()
    if raise_on_exec:
        mock_conn.execute.side_effect = raise_on_exec
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return mock_engine, mock_conn


# ---------------------------------------------------------------------------
# _update_pipeline_stage_sync
# ---------------------------------------------------------------------------

def test_update_pipeline_stage_sync_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_pipeline_stage_sync(1, 2)


def test_update_pipeline_stage_sync_happy():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_pipeline_stage_sync(5, 3)
    conn.execute.assert_called_once()
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_pipeline_stage_sync_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("db"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_pipeline_stage_sync(5, 3)
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_heartbeat_sync
# ---------------------------------------------------------------------------

def test_update_heartbeat_sync_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_heartbeat_sync(1)


def test_update_heartbeat_sync_happy():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_heartbeat_sync(99)
    conn.execute.assert_called_once()
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_heartbeat_sync_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_heartbeat_sync(99)
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_live_status_sync
# ---------------------------------------------------------------------------

def test_update_live_status_sync_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_live_status_sync(1, {"round": 1})


def test_update_live_status_sync_serializes_json():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_live_status_sync(7, {"round": 3, "agents": ["a", "b"]})
    params = conn.execute.call_args.args[1]
    assert '"round": 3' in params["live_status"]
    assert params["job_id"] == 7
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_live_status_sync_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_live_status_sync(7, {"k": 1})
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_pod_id
# ---------------------------------------------------------------------------

def test_update_pod_id_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_pod_id(1, "pod")


def test_update_pod_id_happy():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_pod_id(1, "pod-xyz", gpu_provider="vastai")
    params = conn.execute.call_args.args[1]
    assert params["pod_id"] == "pod-xyz"
    assert params["gpu_provider"] == "vastai"
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_pod_id_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_pod_id(1, "pod")
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_sim_data_available
# ---------------------------------------------------------------------------

def test_update_sim_data_available_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_sim_data_available(1, True)


def test_update_sim_data_available_happy():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_sim_data_available(1, True)
    conn.execute.assert_called_once()
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_sim_data_available_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_sim_data_available(1, False)
    engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_enrichment_sync
# ---------------------------------------------------------------------------

def test_update_enrichment_sync_no_engine():
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=None):
        psp._update_enrichment_sync(1, "text", "[]")


def test_update_enrichment_sync_happy():
    engine, conn = _engine_pair()
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_enrichment_sync(1, "enriched body", '["cite"]')
    params = conn.execute.call_args.args[1]
    assert params["enriched"] == "enriched body"
    assert params["citations"] == '["cite"]'
    conn.commit.assert_called_once()
    engine.dispose.assert_called_once()


def test_update_enrichment_sync_exception():
    engine, _ = _engine_pair(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync_progress._get_sync_engine", return_value=engine):
        psp._update_enrichment_sync(1, "t", "[]")
    engine.dispose.assert_called_once()
