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
