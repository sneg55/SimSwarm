"""Tests for saas.jobs.persistence_async — async DB write helpers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


from saas.jobs import persistence_async


def _mock_factory(session_mock):
    """Return a factory callable that returns an async-context-manager yielding session_mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)

    def factory():
        return cm

    return factory


def _mock_session(execute_result=None, execute_raises=None):
    session = MagicMock()
    if execute_raises:
        session.execute = AsyncMock(side_effect=execute_raises)
    else:
        session.execute = AsyncMock(return_value=execute_result or MagicMock(rowcount=1))
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# _mark_job_failed (async impl routed via _run_async)
# ---------------------------------------------------------------------------

def test_mark_job_failed_no_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        persistence_async._mark_job_failed(1, "boom")  # no raise


def test_mark_job_failed_happy():
    session = _mock_session(execute_result=MagicMock(rowcount=1))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._mark_job_failed(42, "err")
    session.execute.assert_awaited()
    session.commit.assert_awaited()


def test_mark_job_failed_already_terminal_rowcount_zero():
    session = _mock_session(execute_result=MagicMock(rowcount=0))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._mark_job_failed(42, "err")
    session.commit.assert_awaited()


def test_mark_job_failed_swallows_exception():
    session = _mock_session(execute_raises=RuntimeError("db"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._mark_job_failed(42, "err")  # no raise


def test_mark_job_failed_truncates():
    session = _mock_session(execute_result=MagicMock(rowcount=1))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._mark_job_failed(42, "X" * 10000)
    params = session.execute.await_args.args[1]
    assert len(params["error_message"]) == 4096


# ---------------------------------------------------------------------------
# _update_pipeline_stage / _async_update_pipeline_stage
# ---------------------------------------------------------------------------

async def test_async_update_pipeline_stage_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        await persistence_async._async_update_pipeline_stage(1, 2)  # no raise


async def test_async_update_pipeline_stage_running_branch():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_pipeline_stage(1, 3)
    # stage >= 1 → SET status = 'RUNNING'
    sql = str(session.execute.await_args.args[0])
    assert "RUNNING" in sql
    session.commit.assert_awaited()


async def test_async_update_pipeline_stage_zero_branch():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_pipeline_stage(1, 0)
    sql = str(session.execute.await_args.args[0])
    assert "RUNNING" not in sql
    session.commit.assert_awaited()


async def test_async_update_pipeline_stage_exception_swallowed():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_pipeline_stage(1, 2)


def test_update_pipeline_stage_sync_wrapper():
    """The sync wrapper runs the coro via _run_async."""
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_pipeline_stage(1, 2)
    session.execute.assert_awaited()


# ---------------------------------------------------------------------------
# _async_update_pod_id
# ---------------------------------------------------------------------------

async def test_async_update_pod_id_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        await persistence_async._async_update_pod_id(1, "pod")


async def test_async_update_pod_id_happy():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_pod_id(5, "pod-x", gpu_provider="runpod")
    params = session.execute.await_args.args[1]
    assert params["pod_id"] == "pod-x"
    assert params["gpu_provider"] == "runpod"
    session.commit.assert_awaited()


async def test_async_update_pod_id_exception():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_pod_id(5, "pod")


# ---------------------------------------------------------------------------
# _update_job_metadata
# ---------------------------------------------------------------------------

def test_update_job_metadata_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        persistence_async._update_job_metadata(1, "pod")


def test_update_job_metadata_happy():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_job_metadata(1, "pod", provision_seconds=30, pipeline_seconds=120)
    params = session.execute.await_args.args[1]
    assert params["provision_seconds"] == 30
    assert params["pipeline_seconds"] == 120
    session.commit.assert_awaited()


def test_update_job_metadata_exception():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_job_metadata(1, "pod")


# ---------------------------------------------------------------------------
# _update_heartbeat / _async_update_heartbeat
# ---------------------------------------------------------------------------

async def test_async_update_heartbeat_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        await persistence_async._async_update_heartbeat(1)


async def test_async_update_heartbeat_happy():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_heartbeat(1)
    session.commit.assert_awaited()


async def test_async_update_heartbeat_exception():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        await persistence_async._async_update_heartbeat(1)


def test_update_heartbeat_sync_wrapper():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_heartbeat(1)
    session.execute.assert_awaited()


# ---------------------------------------------------------------------------
# _update_enrichment
# ---------------------------------------------------------------------------

def test_update_enrichment_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        persistence_async._update_enrichment(1, "text", "[]")


def test_update_enrichment_happy():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_enrichment(1, "enriched", '["c"]')
    params = session.execute.await_args.args[1]
    assert params["enriched"] == "enriched"
    assert params["citations"] == '["c"]'
    session.commit.assert_awaited()


def test_update_enrichment_exception():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_enrichment(1, "enriched", "[]")


# ---------------------------------------------------------------------------
# _update_job_retry
# ---------------------------------------------------------------------------

def test_update_job_retry_none_factory():
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=None):
        persistence_async._update_job_retry(1, 2)


def test_update_job_retry_happy():
    session = _mock_session()
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_job_retry(1, 3)
    params = session.execute.await_args.args[1]
    assert params["retry_count"] == 3
    session.commit.assert_awaited()


def test_update_job_retry_exception():
    session = _mock_session(execute_raises=RuntimeError("x"))
    factory = _mock_factory(session)
    with patch("saas.jobs.persistence_async._get_worker_session_factory", return_value=factory):
        persistence_async._update_job_retry(1, 2)
