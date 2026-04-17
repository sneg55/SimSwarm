"""Coverage for JobRunner.resume and callback paths."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.jobs.runner import JobRunner, JobConfig


def _cfg(tier="medium"):
    return JobConfig(
        job_id=1, user_id="u", seed_text="s", goal="g", tier=tier,
        model_id="Q", gpu_type="GPU", max_rounds=5, vllm_args="",
        llm_api_key="k", openai_api_key="", neo4j_uri="bolt://",
        neo4j_user="n", neo4j_password="p",
    )


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("saas.jobs.runner.asyncio.sleep", new_callable=AsyncMock), \
         patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
        yield


def _mock_ctx(client):
    ctx = AsyncMock()
    ctx.__aenter__.return_value = client
    ctx.__aexit__.return_value = False
    return ctx


async def test_resume_already_completed():
    gpu = AsyncMock()
    resp = MagicMock()
    resp.json.return_value = {
        "status": "completed", "report": "r",
        "chat_log": "[]", "graph_data": "{}", "structured": "{}",
    }
    client = AsyncMock()
    client.get.return_value = resp

    with patch("saas.jobs.runner.httpx.AsyncClient", return_value=_mock_ctx(client)):
        runner = JobRunner(gpu_provider=gpu)
        result = await runner.resume(pod_id="pod1", job_id=99)

    assert result["status"] == "completed"
    gpu.terminate.assert_called_once_with("pod1")


async def test_resume_pod_unreachable():
    gpu = AsyncMock()
    client = AsyncMock()
    client.get.side_effect = RuntimeError("no route")

    with patch("saas.jobs.runner.httpx.AsyncClient", return_value=_mock_ctx(client)):
        runner = JobRunner(gpu_provider=gpu)
        with pytest.raises(RuntimeError, match="Cannot reach pod"):
            await runner.resume(pod_id="podx", job_id=7)


async def test_resume_failed_status():
    gpu = AsyncMock()
    resp = MagicMock()
    resp.json.return_value = {"status": "failed", "error": "bad\nextra"}
    client = AsyncMock()
    client.get.return_value = resp

    with patch("saas.jobs.runner.httpx.AsyncClient", return_value=_mock_ctx(client)):
        runner = JobRunner(gpu_provider=gpu)
        with pytest.raises(RuntimeError, match="Worker pipeline failed"):
            await runner.resume(pod_id="pod", job_id=5)


async def test_resume_idle_resubmits():
    """Idle pod triggers job config fetch and resubmit."""
    gpu = AsyncMock()
    idle = MagicMock()
    idle.json.return_value = {"status": "idle"}

    completed = MagicMock()
    completed.status_code = 200
    completed.json.return_value = {"status": "completed", "report": "r", "chat_log": "[]"}
    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.json.return_value = {"lines": []}

    # First client used for quick /status check in resume()
    first_client = AsyncMock()
    first_client.get.return_value = idle

    # Second client used by submit_job
    second_client = AsyncMock()
    post_ok = MagicMock()
    post_ok.status_code = 200
    second_client.post.return_value = post_ok

    # Third client used by poll_until_complete
    third_client = AsyncMock()

    def poll_side(url, **kw):
        if "/logs" in url:
            return log_resp
        return completed

    third_client.get.side_effect = poll_side

    clients = iter([
        _mock_ctx(first_client),
        _mock_ctx(second_client),
        _mock_ctx(third_client),
    ])
    from types import SimpleNamespace
    fake_cfg = SimpleNamespace(
        seed_text="s", goal="g", max_rounds=5,
        forecast_days=None, target_agents=5, upload_urls=None, markets_config=None,
    )

    with patch("saas.jobs.runner.httpx.AsyncClient", side_effect=lambda *a, **k: next(clients)), \
         patch("saas.jobs.pipeline.httpx.AsyncClient", side_effect=lambda *a, **k: next(clients, _mock_ctx(third_client))), \
         patch("saas.jobs.persistence._get_job_config_for_resume", return_value=fake_cfg), \
         patch("saas.jobs.pipeline._update_live_status_sync"):
        runner = JobRunner(gpu_provider=gpu)
        result = await runner.resume(pod_id="pod-idle", job_id=12)

    assert result["status"] == "completed"
    gpu.terminate.assert_called_with("pod-idle")


async def test_resume_idle_no_config():
    """Idle pod where DB has no config -> RuntimeError."""
    gpu = AsyncMock()
    idle = MagicMock()
    idle.json.return_value = {"status": "idle"}
    client = AsyncMock()
    client.get.return_value = idle

    with patch("saas.jobs.runner.httpx.AsyncClient", return_value=_mock_ctx(client)), \
         patch("saas.jobs.persistence._get_job_config_for_resume", return_value=None):
        runner = JobRunner(gpu_provider=gpu)
        with pytest.raises(RuntimeError, match="config not found"):
            await runner.resume(pod_id="podi", job_id=5)


async def test_run_stage_callback_invoked():
    """Run() invokes stage_callback at step 0."""
    gpu = AsyncMock()
    gpu.provision.return_value = MagicMock(instance_id="p1")
    gpu.terminate.return_value = None

    seen = []

    async def stage_cb(jid, stage):
        seen.append((jid, stage))

    runner = JobRunner(gpu_provider=gpu, stage_callback=stage_cb)

    async def pipeline_mock(instance_id, cfg):
        return {"report": "", "chat_log": "[]", "graph_data": "{}"}

    runner._execute_pipeline = pipeline_mock
    await runner.run(_cfg())
    assert (1, 0) in seen


async def test_run_pod_id_callback():
    gpu = AsyncMock()

    async def provision(cfg, on_created=None):
        if on_created:
            await on_created("pod-ABC")
        return MagicMock(instance_id="pod-ABC")

    gpu.provision.side_effect = provision
    gpu.terminate.return_value = None

    seen_pod = []

    async def pod_cb(jid, pid):
        seen_pod.append((jid, pid))

    runner = JobRunner(gpu_provider=gpu, pod_id_callback=pod_cb)

    async def pipeline_mock(instance_id, cfg):
        return {"report": "", "chat_log": "[]", "graph_data": "{}"}

    runner._execute_pipeline = pipeline_mock
    await runner.run(_cfg())
    assert (1, "pod-ABC") in seen_pod


async def test_run_timeout_raises():
    """Tier timeout wraps the pipeline. Simulate asyncio.TimeoutError."""
    import asyncio
    gpu = AsyncMock()
    gpu.provision.return_value = MagicMock(instance_id="pod-t")
    gpu.terminate.return_value = None

    runner = JobRunner(gpu_provider=gpu)

    async def slow_pipeline(instance_id, cfg):
        await asyncio.sleep(9999)  # mocked but wait_for wraps

    # wait_for with 0 timeout against already-pending coro raises TimeoutError
    cfg = _cfg(tier="small")
    # Override timeout to 0 via the runner internal: use wait_for patching
    async def raise_timeout(*a, **kw):
        raise asyncio.TimeoutError()

    with patch("saas.jobs.runner.asyncio.wait_for", side_effect=raise_timeout):
        runner._execute_pipeline = slow_pipeline
        with pytest.raises(TimeoutError, match="tier timeout"):
            await runner.run(cfg)

    gpu.terminate.assert_called_with("pod-t")
