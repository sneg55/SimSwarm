"""Tests for the job runner with GPU lifecycle management."""
import pytest
from unittest.mock import AsyncMock

from saas.workers.job_runner import JobConfig, JobRunner, TIER_TIMEOUTS
from saas.gpu.provider import GPUInstance


def _make_job_config(tier: str = "medium") -> JobConfig:
    return JobConfig(
        job_id=42,
        user_id="user-abc",
        seed_text="The world is warming.",
        goal="Analyze climate opinions",
        tier=tier,
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="RTX4090",
        max_rounds=200,
        vllm_args="--max-model-len 16384",
        llm_api_key="sk-test",
        zep_api_key="zep-test",
    )


def _make_instance(instance_id: str = "inst-test") -> GPUInstance:
    return GPUInstance(
        instance_id=instance_id,
        provider="runpod",
        gpu_type="RTX4090",
        ip_address="10.0.0.1",
        ssh_port=22,
        status="running",
    )


def test_timeout_by_tier_small():
    """Small tier has 2700 second timeout."""
    config = _make_job_config(tier="small")
    assert config.timeout_seconds == TIER_TIMEOUTS["small"]
    assert config.timeout_seconds == 2700


def test_timeout_by_tier_medium():
    """Medium tier has 18000 second timeout."""
    config = _make_job_config(tier="medium")
    assert config.timeout_seconds == TIER_TIMEOUTS["medium"]
    assert config.timeout_seconds == 18000


def test_timeout_by_tier_large():
    """Large tier has 43200 second timeout."""
    config = _make_job_config(tier="large")
    assert config.timeout_seconds == TIER_TIMEOUTS["large"]
    assert config.timeout_seconds == 43200


def test_to_mirofish_env_includes_required_keys():
    """to_mirofish_env returns all required environment variables."""
    config = _make_job_config()
    env = config.to_mirofish_env()
    assert "LLM_API_KEY" in env
    assert "LLM_BASE_URL" in env
    assert "LLM_MODEL_NAME" in env
    assert "ZEP_API_KEY" in env
    assert "OASIS_DEFAULT_MAX_ROUNDS" in env
    assert env["LLM_API_KEY"] == "sk-test"
    assert env["ZEP_API_KEY"] == "zep-test"
    assert env["OASIS_DEFAULT_MAX_ROUNDS"] == "200"
    assert env["LLM_MODEL_NAME"] == "Qwen2.5-32B-Instruct-AWQ"


@pytest.mark.asyncio
async def test_run_provisions_gpu():
    """run() calls gpu_provider.provision() with the correct config."""
    gpu_provider = AsyncMock()
    instance = _make_instance("inst-prov")
    gpu_provider.provision.return_value = instance
    gpu_provider.terminate.return_value = None

    runner = JobRunner(gpu_provider=gpu_provider)
    config = _make_job_config()

    # Mock _execute_pipeline to avoid real HTTP calls
    async def mock_pipeline(instance_id, cfg):
        return {"report": "", "chat_log": "[]", "graph_data": "{}"}

    runner._execute_pipeline = mock_pipeline
    await runner.run(config)

    gpu_provider.provision.assert_called_once()
    call_args = gpu_provider.provision.call_args[0][0]
    assert call_args.gpu_type == "RTX4090"
    assert call_args.timeout_seconds == 18000


@pytest.mark.asyncio
async def test_run_terminates_on_success():
    """run() terminates the GPU instance after successful execution."""
    gpu_provider = AsyncMock()
    instance = _make_instance("inst-success")
    gpu_provider.provision.return_value = instance
    gpu_provider.terminate.return_value = None

    runner = JobRunner(gpu_provider=gpu_provider)

    async def mock_pipeline(instance_id, cfg):
        return {"report": "", "chat_log": "[]", "graph_data": "{}"}

    runner._execute_pipeline = mock_pipeline
    await runner.run(_make_job_config())

    gpu_provider.terminate.assert_called_once_with("inst-success")


@pytest.mark.asyncio
async def test_run_terminates_on_failure():
    """run() terminates the GPU instance even when execution fails."""
    gpu_provider = AsyncMock()
    instance = _make_instance("inst-fail")
    gpu_provider.provision.return_value = instance
    gpu_provider.terminate.return_value = None

    runner = JobRunner(gpu_provider=gpu_provider)

    async def mock_pipeline(instance_id, cfg):
        raise RuntimeError("Pipeline crashed")

    runner._execute_pipeline = mock_pipeline
    with pytest.raises(RuntimeError, match="Pipeline crashed"):
        await runner.run(_make_job_config())

    gpu_provider.terminate.assert_called_once_with("inst-fail")
