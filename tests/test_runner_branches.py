"""Coverage for JobRunner callback paths."""
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
