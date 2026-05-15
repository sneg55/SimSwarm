"""Pipeline helper functions: log fetch, health polling, submit_job."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from saas.jobs import pipeline, worker_http


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock), \
            patch("saas.jobs.worker_http.asyncio.sleep", new_callable=AsyncMock):
        yield


async def test_log_worker_output_with_client():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"lines": ["one", "two"]}
    client = AsyncMock()
    client.get.return_value = resp
    await worker_http.log_worker_output("http://w", client=client)
    client.get.assert_called_once()


async def test_log_worker_output_swallows_errors():
    client = AsyncMock()
    client.get.side_effect = RuntimeError("boom")
    # Should not raise
    await worker_http.log_worker_output("http://w", client=client)


async def test_log_worker_output_no_client():
    mock_client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"lines": []}
    mock_client.get.return_value = resp
    ctx = AsyncMock()
    ctx.__aenter__.return_value = mock_client
    ctx.__aexit__.return_value = False
    with patch("saas.jobs.worker_http.httpx.AsyncClient", return_value=ctx):
        await worker_http.log_worker_output("http://w")


async def test_wait_for_worker_health_ready():
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"vllm_ready": True}
    ok.headers = {"content-type": "application/json"}
    client = AsyncMock()
    client.get.return_value = ok

    await worker_http.wait_for_worker_health("http://w", client)


async def test_wait_for_worker_health_connect_error_then_timeout():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("down")
    with pytest.raises(TimeoutError):
        await worker_http.wait_for_worker_health("http://w", client)


async def test_wait_for_worker_health_generic_exception():
    client = AsyncMock()
    client.get.side_effect = RuntimeError("weird")
    with pytest.raises(TimeoutError):
        await worker_http.wait_for_worker_health("http://w", client)


async def test_submit_job_success():
    class Cfg:
        seed_text = "s"
        goal = "g"
        max_rounds = 10
        forecast_days = None
        target_agents = 5
        upload_urls = None
        markets_config = None
        timeout_seconds = 3600

    ok = MagicMock()
    ok.status_code = 200
    client = AsyncMock()
    client.post.return_value = ok

    await worker_http.submit_job("http://w", Cfg(), client)


async def test_submit_job_rejected_json_body():
    class Cfg:
        seed_text = "s"
        goal = "g"
        max_rounds = 10
        forecast_days = None
        target_agents = 5
        upload_urls = None
        markets_config = None
        timeout_seconds = 3600

    resp = MagicMock()
    resp.status_code = 400
    resp.json.return_value = {"error": "bad-payload"}
    resp.text = "bad"

    client = AsyncMock()
    client.post.return_value = resp

    with pytest.raises(RuntimeError, match="bad-payload"):
        await worker_http.submit_job("http://w", Cfg(), client)


async def test_submit_job_tolerates_already_running():
    """If the worker returns 409 'A job is already running', that means the
    recover task has already claimed the pod — the main task should not fail,
    it should fall through so poll_until_complete watches the same job."""
    class Cfg:
        seed_text = "s"
        goal = "g"
        max_rounds = 10
        forecast_days = None
        target_agents = 5
        upload_urls = None
        markets_config = None
        timeout_seconds = 3600

    resp = MagicMock()
    resp.status_code = 409
    resp.json.return_value = {"error": "A job is already running"}
    resp.text = "A job is already running"

    client = AsyncMock()
    client.post.return_value = resp

    # Should NOT raise — main task hands off to polling.
    await worker_http.submit_job("http://w", Cfg(), client)


async def test_submit_job_rejected_text_body():
    class Cfg:
        seed_text = "s"
        goal = "g"
        max_rounds = 10
        forecast_days = None
        target_agents = 5
        upload_urls = None
        markets_config = None
        timeout_seconds = 3600

    resp = MagicMock()
    resp.status_code = 500
    resp.json.side_effect = ValueError("not json")
    resp.text = "Internal server error text"

    client = AsyncMock()
    client.post.return_value = resp

    with pytest.raises(RuntimeError, match="Internal server error text"):
        await worker_http.submit_job("http://w", Cfg(), client)


async def test_poll_until_complete_failed_status():
    class Cfg:
        job_id = 1
        timeout_seconds = 30
        max_rounds = 5

    failed = MagicMock()
    failed.status_code = 200
    failed.json.return_value = {"status": "failed", "error": "pipeline exploded\nmore", "stdout": "some"}
    log = MagicMock()
    log.status_code = 200
    log.json.return_value = {"lines": []}

    def side(url, **kw):
        if "/logs" in url:
            return log
        return failed

    client = AsyncMock()
    client.get.side_effect = side

    with pytest.raises(RuntimeError, match="pipeline exploded"):
        await pipeline.poll_until_complete("http://w", "pod1", Cfg(), client=client)


async def test_poll_until_complete_circuit_breaker():
    class Cfg:
        job_id = 1
        timeout_seconds = 30
        max_rounds = 5

    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("down")

    with pytest.raises(RuntimeError, match="pod_unreachable"):
        await pipeline.poll_until_complete("http://w", "pod", Cfg(), client=client)


async def test_poll_until_complete_completes():
    class Cfg:
        job_id = 1
        timeout_seconds = 30
        max_rounds = 5

    completed = MagicMock()
    completed.status_code = 200
    completed.json.return_value = {
        "status": "completed",
        "report": "# report",
        "chat_log": "[]",
        "graph_data": "{}",
        "structured": "{}",
        "sim_data_uploaded": True,
    }
    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.json.return_value = {"lines": ["Generating ontology"]}

    def side(url, **kw):
        if "/logs" in url:
            return log_resp
        if "/partial_chat" in url:
            pc = MagicMock()
            pc.status_code = 200
            pc.json.return_value = {"messages": [{"x": 1}]}
            return pc
        return completed

    client = AsyncMock()
    client.get.side_effect = side

    stage_calls = []
    heartbeat_calls = []

    async def stage_cb(jid, stage):
        stage_calls.append((jid, stage))

    async def hb_cb(jid):
        heartbeat_calls.append(jid)

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", Cfg(), client=client,
            stage_callback=stage_cb, heartbeat_callback=hb_cb,
        )
    assert result["status"] == "completed"
    assert result["sim_data_uploaded"] is True


async def test_poll_until_complete_no_client():
    """Test the backward-compat path where caller doesn't supply a client."""
    class Cfg:
        job_id = 1
        timeout_seconds = 30

    completed = MagicMock()
    completed.status_code = 200
    completed.json.return_value = {"status": "completed", "report": "r", "chat_log": "[]"}
    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.json.return_value = {"lines": []}

    mock_client = AsyncMock()

    def side(url, **kw):
        if "/logs" in url:
            return log_resp
        return completed

    mock_client.get.side_effect = side
    ctx = AsyncMock()
    ctx.__aenter__.return_value = mock_client
    ctx.__aexit__.return_value = False

    with patch("saas.jobs.worker_http.httpx.AsyncClient", return_value=ctx):
        with patch("saas.jobs.pipeline._update_live_status_sync"):
            result = await pipeline.poll_until_complete("http://w", "pod", Cfg())
    assert result["status"] == "completed"
