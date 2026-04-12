"""Tests for saas.jobs.persistence_sync (psycopg2/sync helpers)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from saas.jobs import persistence_sync


def _make_mock_engine(exec_result=None, raise_on_exec=None):
    """Return (mock_engine, mock_conn) pair with working context-manager protocol."""
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
# _mark_job_failed_sync
# ---------------------------------------------------------------------------

def test_mark_job_failed_sync_no_engine():
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=None):
        persistence_sync._mark_job_failed_sync(1, "boom")  # no raise


def test_mark_job_failed_sync_happy_path():
    result = MagicMock(rowcount=1)
    mock_engine, mock_conn = _make_mock_engine(exec_result=result)
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._mark_job_failed_sync(42, "err")
    mock_conn.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()


def test_mark_job_failed_sync_already_terminal_logs():
    """rowcount=0 triggers the info-log branch."""
    result = MagicMock(rowcount=0)
    mock_engine, mock_conn = _make_mock_engine(exec_result=result)
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._mark_job_failed_sync(42, "err")
    mock_engine.dispose.assert_called_once()


def test_mark_job_failed_sync_truncates_long_error():
    long_msg = "X" * 10000
    result = MagicMock(rowcount=1)
    mock_engine, mock_conn = _make_mock_engine(exec_result=result)
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._mark_job_failed_sync(42, long_msg)
    call_kwargs = mock_conn.execute.call_args.args[1]
    assert len(call_kwargs["error_message"]) == 4096


def test_mark_job_failed_sync_exception_is_swallowed():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("db down"))
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._mark_job_failed_sync(42, "boom")  # does not raise
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _save_job_results
# ---------------------------------------------------------------------------

def test_save_job_results_no_engine():
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=None):
        persistence_sync._save_job_results(1, "r", "[]")  # no raise


def test_save_job_results_happy():
    mock_engine, mock_conn = _make_mock_engine(exec_result=MagicMock())
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._save_job_results(1, "report", "[]", graph_data="{}", key_insight="k", structured="{}")
    mock_conn.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()


def test_save_job_results_exception_swallowed():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._save_job_results(1, "r", "[]")
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _update_job_retry_sync
# ---------------------------------------------------------------------------

def test_update_job_retry_sync_no_engine():
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=None):
        persistence_sync._update_job_retry_sync(1, 2)


def test_update_job_retry_sync_happy():
    mock_engine, mock_conn = _make_mock_engine(exec_result=MagicMock())
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._update_job_retry_sync(1, 2)
    mock_conn.commit.assert_called_once()
    mock_engine.dispose.assert_called_once()


def test_update_job_retry_sync_exception():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("x"))
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        persistence_sync._update_job_retry_sync(1, 2)
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _get_job_status
# ---------------------------------------------------------------------------

def test_get_job_status_no_engine():
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=None):
        assert persistence_sync._get_job_status(1) is None


def test_get_job_status_row_found():
    result = MagicMock()
    result.first.return_value = ("RUNNING",)
    mock_engine, mock_conn = _make_mock_engine(exec_result=result)
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        assert persistence_sync._get_job_status(1) == "RUNNING"
    mock_engine.dispose.assert_called_once()


def test_get_job_status_no_row():
    result = MagicMock()
    result.first.return_value = None
    mock_engine, _ = _make_mock_engine(exec_result=result)
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        assert persistence_sync._get_job_status(1) is None
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------------
# _get_job_config_for_resume
# ---------------------------------------------------------------------------

def test_get_job_config_for_resume_no_engine():
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=None):
        assert persistence_sync._get_job_config_for_resume(1) is None


def test_get_job_config_for_resume_not_found():
    result = MagicMock()
    result.first.return_value = None
    mock_engine, mock_conn = _make_mock_engine()
    mock_conn.execute.return_value = result
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        assert persistence_sync._get_job_config_for_resume(1) is None
    mock_engine.dispose.assert_called_once()


def test_get_job_config_for_resume_exception_returns_none():
    mock_engine, _ = _make_mock_engine(raise_on_exec=RuntimeError("db err"))
    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine):
        assert persistence_sync._get_job_config_for_resume(1) is None
    mock_engine.dispose.assert_called_once()


def test_get_job_config_for_resume_happy_path():
    row = (
        "seed text here",
        "my goal",
        "small",
        None,  # enriched_seed
        7,     # forecast_days
        15,    # max_rounds
        10,    # target_agents
    )
    result = MagicMock()
    result.first.return_value = row
    mock_engine, mock_conn = _make_mock_engine()
    mock_conn.execute.return_value = result

    mock_storage = MagicMock()
    mock_storage.generate_upload_urls.return_value = {"posts": "http://x"}

    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine), \
         patch("saas.storage.minio_client.SimDataStorage", return_value=mock_storage), \
         patch("saas.config.Settings") as mock_settings_cls:
        mock_settings_cls.return_value = MagicMock(
            MINIO_ENDPOINT="localhost:9000",
            MINIO_ACCESS_KEY="k",
            MINIO_SECRET_KEY="s",
            MINIO_BUCKET="b",
            MINIO_SECURE=False,
            MINIO_PROXY_BASE=None,
        )
        config = persistence_sync._get_job_config_for_resume(42)

    assert config is not None
    assert config.seed_text == "seed text here"
    assert config.goal == "my goal"
    assert config.max_rounds == 15
    assert config.target_agents == 10
    assert config.forecast_days == 7
    assert config.upload_urls == {"posts": "http://x"}
    mock_engine.dispose.assert_called_once()


def test_get_job_config_for_resume_uses_enriched_seed_when_set():
    row = ("raw seed", "g", "small", "enriched!", None, None, None)
    result = MagicMock()
    result.first.return_value = row
    mock_engine, mock_conn = _make_mock_engine()
    mock_conn.execute.return_value = result
    mock_storage = MagicMock()
    mock_storage.generate_upload_urls.return_value = {}

    with patch("saas.jobs.persistence_sync._get_sync_engine", return_value=mock_engine), \
         patch("saas.storage.minio_client.SimDataStorage", return_value=mock_storage), \
         patch("saas.config.Settings", return_value=MagicMock(
             MINIO_ENDPOINT="x", MINIO_ACCESS_KEY="x", MINIO_SECRET_KEY="x",
             MINIO_BUCKET="x", MINIO_SECURE=False, MINIO_PROXY_BASE=None,
         )):
        config = persistence_sync._get_job_config_for_resume(42)

    assert config.seed_text == "enriched!"
    # Defaults applied when routing row is missing fields
    assert config.max_rounds == 15
    assert config.target_agents == 5
