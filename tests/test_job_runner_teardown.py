"""Tests for JobRunner teardown guarantees."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.jobs.runner import JobRunner, JobConfig


def _make_config(**overrides):
    defaults = dict(
        job_id=1, user_id="u1", seed_text="test seed", goal="test goal",
        tier="small", model_id="test-model", gpu_type="RTX4090",
        max_rounds=10, vllm_args="", llm_api_key="k", openai_api_key="",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


@pytest.fixture
def mock_gpu_provider():
    provider = AsyncMock()
    instance = MagicMock()
    instance.instance_id = "pod-abc123"

    async def _provision(config, on_created=None):
        if on_created:
            await on_created(instance.instance_id)
        return instance

    provider.provision.side_effect = _provision
    provider.terminate.return_value = None
    return provider


async def test_pod_id_callback_called_before_pipeline(mock_gpu_provider):
    """pod_id_callback must fire immediately after provisioning, before pipeline starts."""
    callback_calls = []

    async def pod_id_cb(job_id, pod_id):
        callback_calls.append((job_id, pod_id))

    runner = JobRunner(
        gpu_provider=mock_gpu_provider,
        pod_id_callback=pod_id_cb,
    )
    runner._execute_pipeline = AsyncMock(side_effect=RuntimeError("pipeline boom"))

    with pytest.raises(RuntimeError, match="pipeline boom"):
        await runner.run(_make_config())

    assert callback_calls == [(1, "pod-abc123")]
    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")


async def test_terminate_called_on_pipeline_timeout(mock_gpu_provider):
    """GPU must be terminated even when the pipeline times out."""
    async def slow_pipeline(*args, **kwargs):
        await asyncio.sleep(10)

    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = slow_pipeline

    config = _make_config()
    config._timeout_override = 0.1

    with pytest.raises(TimeoutError):
        await runner.run(config)

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")


async def test_terminate_called_on_pipeline_error(mock_gpu_provider):
    """GPU must be terminated when pipeline raises any exception."""
    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = AsyncMock(side_effect=RuntimeError("vLLM crash"))

    with pytest.raises(RuntimeError, match="vLLM crash"):
        await runner.run(_make_config())

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")


async def test_pipeline_error_preserved_when_terminate_fails(mock_gpu_provider):
    """If gpu_provider.terminate() raises during teardown, the original
    pipeline error must propagate — not the terminate error.

    Regression: an unguarded `await self.gpu_provider.terminate(pod_id)` in
    finally lets Python overwrite the active exception. Users then see e.g.
    'pod not found to terminate' instead of the real failure (OOM, crash).
    """
    mock_gpu_provider.terminate.side_effect = RuntimeError("pod not found to terminate")
    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = AsyncMock(side_effect=RuntimeError("vLLM OOM"))

    with pytest.raises(RuntimeError, match="vLLM OOM"):
        await runner.run(_make_config())

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")


async def test_terminate_called_on_asyncio_cancellation(mock_gpu_provider):
    """GPU must be terminated even when the task is cancelled externally."""
    cancel_event = asyncio.Event()

    async def hanging_pipeline(*args, **kwargs):
        cancel_event.set()
        await asyncio.sleep(3600)

    runner = JobRunner(gpu_provider=mock_gpu_provider)
    runner._execute_pipeline = hanging_pipeline

    config = _make_config()
    task = asyncio.create_task(runner.run(config))

    await cancel_event.wait()
    task.cancel()

    with pytest.raises((asyncio.CancelledError, TimeoutError)):
        await task

    mock_gpu_provider.terminate.assert_awaited_once_with("pod-abc123")
