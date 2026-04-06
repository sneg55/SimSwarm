"""
Tests for JobRunner._execute_pipeline() HTTP job submission and response handling.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestExecutePipelineHTTP:
    """Verify _execute_pipeline() HTTP job submission and response parsing."""

    @pytest.fixture(autouse=True)
    def _mock_sleep(self):
        """Mock asyncio.sleep for all pipeline tests to avoid real delays."""
        with patch("saas.jobs.runner.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_polls_health_before_submitting(self):
        """_execute_pipeline polls /health before posting to /job."""
        mock_ctx, mock_client = _make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner._execute_pipeline("pod-123", config)

        # Should have called GET /health
        health_calls = [
            c for c in mock_client.get.call_args_list
            if "/health" in str(c)
        ]
        assert len(health_calls) >= 1

    @pytest.mark.asyncio
    async def test_submits_job_with_correct_payload(self):
        """Job POST includes seed_text, goal, and max_rounds."""
        mock_ctx, mock_client = _make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(
            seed_text="Test seed material",
            goal="Research objective",
            max_rounds=42,
        )

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner._execute_pipeline("pod-456", config)

        post_call = mock_client.post.call_args
        assert post_call is not None
        payload = post_call.kwargs.get("json") or post_call[1].get("json") or post_call[0][1]
        assert payload["seed_text"] == "Test seed material"
        assert payload["goal"] == "Research objective"
        assert payload["max_rounds"] == 42

    @pytest.mark.asyncio
    async def test_uses_correct_runpod_proxy_url(self):
        """Worker URL is constructed as https://{pod_id}-5000.proxy.runpod.net."""
        mock_ctx, mock_client = _make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner._execute_pipeline("mypod-789", config)

        post_call = mock_client.post.call_args
        url = post_call[0][0] if post_call[0] else post_call.args[0]
        assert "mypod-789-5000.proxy.runpod.net" in url

    @pytest.mark.asyncio
    async def test_returns_report_and_chat_log(self):
        """Result dict has report and chat_log from the HTTP response."""
        mock_ctx, _ = _make_mock_http_client(job_response={
            "status": "completed",
            "report": "# My Report Content",
            "chat_log": '[{"action":"comment"}]',
        })
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(job_id=99)

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            result = await runner._execute_pipeline("pod-ret", config)

        assert result["report"] == "# My Report Content"
        assert result["chat_log"] == '[{"action":"comment"}]'

    @pytest.mark.asyncio
    async def test_returns_job_id_and_instance_id(self):
        """Result also carries job_id and instance_id for traceability."""
        mock_ctx, _ = _make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(job_id=555)

        with patch("saas.jobs.runner.httpx.AsyncClient", return_value=mock_ctx):
            result = await runner._execute_pipeline("inst-555", config)

        assert result["job_id"] == 555
        assert result["instance_id"] == "inst-555"
