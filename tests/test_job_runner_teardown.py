"""Tests for JobRunner teardown guarantees."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.workers.job_runner import JobRunner, JobConfig


def _make_config(**overrides):
    defaults = dict(
        job_id=1, user_id="u1", seed_text="test seed", goal="test goal",
        tier="small", model_id="test-model", gpu_type="RTX4090",
        max_rounds=10, vllm_args="", llm_api_key="k", zep_api_key="z",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


@pytest.fixture
def mock_gpu_provider():
    provider = AsyncMock()
    instance = MagicMock()
    instance.instance_id = "pod-abc123"
    provider.provision.return_value = instance
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
