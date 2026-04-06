"""
Tests for JobRunner pipeline lifecycle: health polling retries, timeouts,
and GPU instance teardown on success/failure.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.gpu.provider import GPUInstance
from saas.jobs.runner import JobConfig, JobRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job_config(**overrides) -> JobConfig:
    defaults = dict(
        job_id=1,
        user_id="user-test",
        seed_text="Climate change is accelerating.",
        goal="Analyse public opinion about climate",
        tier="medium",
        model_id="Qwen2.5-32B-Instruct-AWQ",
        gpu_type="RTX4090",
        max_rounds=50,
        vllm_args="",
        llm_api_key="sk-test",
        openai_api_key="",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
    )
    defaults.update(overrides)
    return JobConfig(**defaults)


def _make_instance(instance_id: str = "inst-abc") -> GPUInstance:
    return GPUInstance(
        instance_id=instance_id,
        provider="runpod",
        gpu_type="RTX4090",
        ip_address=f"https://{instance_id}-5000.proxy.runpod.net",
        ssh_port=None,
        status="running",
    )


def _make_mock_http_client(health_status=200, job_response=None):
    """Create a mock httpx.AsyncClient context manager.

    GET /health returns health_status, GET /status returns the job_response
    (which must include a "status" key), POST /job returns 200.
    """
    if job_response is None:
        job_response = {
            "status": "completed",
            "report": "# Report",
            "chat_log": '[{"action":"post"}]',
        }

    health_resp = MagicMock()
    health_resp.status_code = health_status
    health_resp.json.return_value = {"status": "ok", "vllm_ready": True}
    health_resp.headers = {"content-type": "application/json"}

    status_resp = MagicMock()
    status_resp.status_code = 200
    status_resp.json.return_value = job_response

    log_resp = MagicMock()
    log_resp.status_code = 200
    log_resp.json.return_value = {"lines": [], "total_lines": 0, "job_status": "completed"}

    post_resp = MagicMock()
    post_resp.status_code = 200
    post_resp.json.return_value = {"status": "accepted"}
    post_resp.raise_for_status = MagicMock()

    def get_side_effect(url, **kwargs):
        if "/health" in url:
            return health_resp
        elif "/logs" in url:
            return log_resp
        else:
            return status_resp

    mock_client = AsyncMock()
    mock_client.get.side_effect = get_side_effect
    mock_client.post.return_value = post_resp

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client
    mock_ctx.__aexit__.return_value = False
    return mock_ctx, mock_client


# ===========================================================================
# Tests
# ===========================================================================


class TestPipelineLifecycle:
    """Health polling retries, timeouts, and GPU teardown guarantees."""

    @pytest.fixture(autouse=True)
    def _mock_sleep(self):
        """Mock asyncio.sleep for all pipeline tests to avoid real delays."""
        with patch("saas.jobs.runner.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_health_polling_retries_on_failure(self):
        """Health polling retries when the worker API is not yet up."""
        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.json.return_value = {"status": "waiting_for_vllm", "vllm_ready": False}
        fail_resp.headers = {"content-type": "application/json"}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"status": "ok", "vllm_ready": True}
        ok_resp.headers = {"content-type": "application/json"}

        status_resp = MagicMock()
        status_resp.status_code = 200
        status_resp.json.return_value = {"status": "completed", "report": "", "chat_log": "[]"}

        log_resp = MagicMock()
        log_resp.status_code = 200
        log_resp.json.return_value = {"lines": [], "total_lines": 0, "job_status": "completed"}

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"status": "accepted"}
        post_resp.raise_for_status = MagicMock()

        # Health fails once then succeeds, status always returns completed
        health_responses = iter([fail_resp, ok_resp])

        def get_side_effect(url, **kwargs):
            if "/health" in url:
                return next(health_responses)
            elif "/logs" in url:
                return log_resp
            else:
                return status_resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = get_side_effect
        mock_client.post.return_value = post_resp

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__.return_value = False

        gpu = AsyncMock()
        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner._execute_pipeline("pod-retry", config)

        # Should have called get at least 3 times (2 health + 1 status)
        assert mock_client.get.call_count >= 3

    @pytest.mark.asyncio
    async def test_timeout_raised_if_health_never_ready(self):
        """TimeoutError is raised if worker API never becomes healthy."""
        fail_resp = MagicMock()
        fail_resp.status_code = 503

        mock_client = AsyncMock()
        mock_client.get.return_value = fail_resp

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__.return_value = False

        gpu = AsyncMock()
        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(TimeoutError, match="did not become ready"):
                await runner._execute_pipeline("pod-timeout", config)

    @pytest.mark.asyncio
    async def test_full_run_terminates_gpu_on_success(self):
        """runner.run() terminates the GPU instance after pipeline completes."""
        mock_ctx, _ = _make_mock_http_client()
        gpu = AsyncMock()
        instance = _make_instance("inst-full")
        gpu.provision.return_value = instance
        gpu.terminate.return_value = None

        runner = JobRunner(gpu_provider=gpu)

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner.run(_make_job_config())

        gpu.terminate.assert_called_once_with("inst-full")

    @pytest.mark.asyncio
    async def test_full_run_terminates_gpu_on_failure(self):
        """runner.run() terminates the GPU instance even if pipeline raises."""
        gpu = AsyncMock()
        instance = _make_instance("inst-fail")
        gpu.provision.return_value = instance
        gpu.terminate.return_value = None

        runner = JobRunner(gpu_provider=gpu)

        # Make the health check always fail so TimeoutError is raised
        fail_resp = MagicMock()
        fail_resp.status_code = 503
        mock_client = AsyncMock()
        mock_client.get.return_value = fail_resp
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__.return_value = False

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(TimeoutError):
                await runner.run(_make_job_config())

        gpu.terminate.assert_called_once_with("inst-fail")
