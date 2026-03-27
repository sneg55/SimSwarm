"""Tests for RunPod hardening: new DB columns and error classification."""
import os
from unittest.mock import patch, AsyncMock

import httpx
import pytest

from saas.gpu.errors import TransientGPUError, PermanentGPUError, classify_gpu_error
from saas.gpu.provider import GPUInstance
from saas.models.job import SimulationJob
from saas.workers.job_runner import JobConfig, JobRunner, get_worker_image


# ── Task 1: DB Schema — New Columns on SimulationJob ──


async def test_simulation_job_has_pod_id_column(db_session):
    job = SimulationJob(
        user_id="user-1", seed_text="test", goal="test",
        tier="small", credits_charged=30, pod_id="pod_abc123",
    )
    db_session.add(job)
    await db_session.flush()
    assert job.pod_id == "pod_abc123"


async def test_simulation_job_has_retry_count_column(db_session):
    job = SimulationJob(
        user_id="user-1", seed_text="test", goal="test",
        tier="small", credits_charged=30, retry_count=0,
    )
    db_session.add(job)
    await db_session.flush()
    assert job.retry_count == 0


async def test_simulation_job_has_duration_columns(db_session):
    job = SimulationJob(
        user_id="user-1", seed_text="test", goal="test",
        tier="small", credits_charged=30,
        provision_seconds=45, pipeline_seconds=320,
    )
    db_session.add(job)
    await db_session.flush()
    assert job.provision_seconds == 45
    assert job.pipeline_seconds == 320


# ── Task 2: Error Classification Module ──


def test_classify_timeout_as_transient():
    assert classify_gpu_error(TimeoutError("pod did not become ready")) == "transient"


def test_classify_connect_error_as_transient():
    assert classify_gpu_error(httpx.ConnectError("connection refused")) == "transient"


def test_classify_runtime_error_pipeline_failed_as_permanent():
    assert classify_gpu_error(RuntimeError("Worker pipeline failed: OOM killed")) == "permanent"


def test_classify_runtime_error_no_gpus_as_transient():
    assert classify_gpu_error(RuntimeError("No RunPod GPUs available. Last: insufficient capacity")) == "transient"


def test_classify_runtime_error_worker_rejected_as_permanent():
    assert classify_gpu_error(RuntimeError("Worker rejected job: invalid seed format")) == "permanent"


def test_transient_gpu_error_is_exception():
    assert isinstance(TransientGPUError("timeout"), Exception)


def test_permanent_gpu_error_is_exception():
    assert isinstance(PermanentGPUError("bad input"), Exception)


# ── Task 3: Env-Based Worker Image Tag ──


def test_worker_image_from_env_var():
    with patch.dict(os.environ, {"WORKER_IMAGE_TAG": "abc123"}):
        assert get_worker_image() == "ghcr.io/sneg55/simswarm-worker:abc123"


def test_worker_image_fallback_without_env_var():
    env = os.environ.copy()
    env.pop("WORKER_IMAGE_TAG", None)
    with patch.dict(os.environ, env, clear=True):
        result = get_worker_image()
        assert result.startswith("ghcr.io/sneg55/simswarm-worker:")


# ── Task 4: JobRunner Returns pod_id and Durations ──


@pytest.mark.asyncio
async def test_job_runner_result_includes_pod_id():
    gpu = AsyncMock()
    gpu.provision.return_value = GPUInstance(
        instance_id="pod_xyz", provider="runpod", gpu_type="RTX4090",
        ip_address="https://pod_xyz-5000.proxy.runpod.net", ssh_port=None, status="running",
    )
    runner = JobRunner(gpu_provider=gpu)

    async def mock_pipeline(instance_id, config):
        return {"report": "test", "chat_log": "[]", "graph_data": "{}"}
    runner._execute_pipeline = mock_pipeline

    config = JobConfig(
        job_id=1, user_id="u1", seed_text="test", goal="test", tier="small",
        model_id="m", gpu_type="RTX4090", max_rounds=10, vllm_args="",
        llm_api_key="k", zep_api_key="z",
    )
    result = await runner.run(config)
    assert result["pod_id"] == "pod_xyz"
    assert "provision_seconds" in result
    assert "pipeline_seconds" in result


# ── Task 5: Celery Task — Retry Logic + Persist Metadata ──


def test_task_has_max_retries_1():
    from saas.workers.tasks import run_simulation_task
    assert run_simulation_task.max_retries == 1


# ── Task 6: Rewrite Orphan Pod Cleanup ──


def test_cleanup_terminates_pod_not_in_active_jobs():
    from saas.workers.tasks import cleanup_orphaned_pods
    mock_pods = [{"id": "pod_orphan", "name": "fishcloud-sim", "machine": {"gpuDisplayName": "A100"}}]
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-key", "DATABASE_URL": ""}):
        with patch("runpod.get_pods", return_value=mock_pods):
            with patch("runpod.terminate_pod") as mock_terminate:
                with patch("saas.workers.tasks._get_active_job_pod_ids", return_value=set()):
                    result = cleanup_orphaned_pods()
    mock_terminate.assert_called_once_with("pod_orphan")


def test_cleanup_preserves_pod_with_active_job():
    from saas.workers.tasks import cleanup_orphaned_pods
    mock_pods = [{"id": "pod_active", "name": "fishcloud-sim", "machine": {"gpuDisplayName": "A100"}}]
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-key", "DATABASE_URL": ""}):
        with patch("runpod.get_pods", return_value=mock_pods):
            with patch("runpod.terminate_pod") as mock_terminate:
                with patch("saas.workers.tasks._get_active_job_pod_ids", return_value={"pod_active"}):
                    result = cleanup_orphaned_pods()
    mock_terminate.assert_not_called()
