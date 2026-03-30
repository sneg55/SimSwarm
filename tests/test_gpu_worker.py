"""
Tests for the GPU worker pipeline wiring:
  - run_job.py argument parsing
  - worker_api.py Flask endpoints
  - JobRunner._execute_pipeline() HTTP approach (mocked httpx)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.gpu.provider import GPUInstance
from saas.workers.job_runner import JobConfig, JobRunner

# ---------------------------------------------------------------------------
# Helpers shared by both test sections
# ---------------------------------------------------------------------------

RUN_JOB_PATH = Path(__file__).parent.parent / "infra" / "docker" / "run_job.py"
WORKER_API_PATH = Path(__file__).parent.parent / "infra" / "docker" / "worker_api.py"


def _load_run_job_module():
    """Dynamically import run_job.py without executing __main__."""
    spec = importlib.util.spec_from_file_location("run_job", RUN_JOB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


# ===========================================================================
# Section 1: run_job.py argument parsing
# ===========================================================================


class TestRunJobArgParsing:
    """Verify that run_job.py's argparse setup accepts the expected CLI flags."""

    def _parse(self, args: list[str]):
        _load_run_job_module()  # verify it loads without error
        # Temporarily replace sys.argv so argparse reads our list
        original_argv = sys.argv[:]
        sys.argv = ["run_job.py"] + args
        try:
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--seed-file", required=True)
            parser.add_argument("--goal", required=True)
            parser.add_argument("--max-rounds", type=int, default=200)
            parser.add_argument("--output-dir", default="/tmp/results")
            parser.add_argument("--skip-vllm-wait", action="store_true")
            return parser.parse_args(args)
        finally:
            sys.argv = original_argv

    def test_required_args_parsed(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "Test goal"])
        assert ns.seed_file == "/tmp/seed.txt"
        assert ns.goal == "Test goal"

    def test_default_max_rounds(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.max_rounds == 200

    def test_custom_max_rounds(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G", "--max-rounds", "42"])
        assert ns.max_rounds == 42

    def test_default_output_dir(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.output_dir == "/tmp/results"

    def test_custom_output_dir(self):
        ns = self._parse([
            "--seed-file", "/tmp/seed.txt",
            "--goal", "G",
            "--output-dir", "/custom/path",
        ])
        assert ns.output_dir == "/custom/path"

    def test_skip_vllm_wait_flag(self):
        ns = self._parse([
            "--seed-file", "/tmp/seed.txt",
            "--goal", "G",
            "--skip-vllm-wait",
        ])
        assert ns.skip_vllm_wait is True

    def test_skip_vllm_wait_defaults_false(self):
        ns = self._parse(["--seed-file", "/tmp/seed.txt", "--goal", "G"])
        assert ns.skip_vllm_wait is False

    def test_run_job_file_exists(self):
        assert RUN_JOB_PATH.exists(), f"run_job.py not found at {RUN_JOB_PATH}"


# ===========================================================================
# Section 2: worker_api.py Flask endpoints
# ===========================================================================


class TestWorkerApi:
    """Test the worker Flask API endpoints."""

    @pytest.fixture()
    def client(self):
        """Create a Flask test client with a fresh job state."""
        spec = importlib.util.spec_from_file_location("worker_api", WORKER_API_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._job["status"] = "idle"
        mod._job["result"] = None
        mod._job["error"] = None
        mod.app.config["TESTING"] = True
        return mod.app.test_client(), mod

    def test_health_returns_ok(self, client):
        flask_client, _ = client
        # Mock vLLM health check — /health imports requests locally
        mock_vllm_resp = MagicMock()
        mock_vllm_resp.status_code = 200
        with patch("requests.get", return_value=mock_vllm_resp):
            resp = flask_client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["vllm_ready"] is True
        assert data["job_status"] == "idle"

    def test_status_endpoint(self, client):
        flask_client, _ = client
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_job_conflict_when_running(self, client):
        flask_client, mod = client
        mod._job["status"] = "running"
        resp = flask_client.post(
            "/job",
            json={"seed_text": "text", "goal": "goal", "max_rounds": 10},
        )
        assert resp.status_code == 409
        assert "already running" in resp.get_json()["error"]

    def test_job_accepted(self, client, tmp_path):
        """POST /job returns accepted immediately (pipeline runs in background)."""
        flask_client, mod = client
        # Point LOG_FILE to a temp location and mock the thread
        mod.LOG_FILE = tmp_path / "pipeline.log"
        mod.LOG_FILE.write_text("")
        with patch.object(mod.threading, "Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            resp = flask_client.post(
                "/job",
                json={"seed_text": "Climate", "goal": "Analyse", "max_rounds": 10},
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "accepted"

    def test_status_returns_completed_with_results(self, client):
        """GET /status returns report + chat_log when job is completed."""
        flask_client, mod = client
        with mod._lock:
            mod._job["status"] = "completed"
            mod._job["result"] = {
                "report": "# Report\nDone.",
                "chat_log": '[{"action":"post"}]',
                "graph_data": "{}",
            }
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert data["report"] == "# Report\nDone."
        assert data["chat_log"] == '[{"action":"post"}]'

    def test_status_returns_failed_with_error(self, client):
        """GET /status returns error when job has failed."""
        flask_client, mod = client
        with mod._lock:
            mod._job["status"] = "failed"
            mod._job["error"] = "Fatal error: something went wrong"
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "Fatal error" in data["error"]

    def test_worker_api_file_exists(self):
        assert WORKER_API_PATH.exists(), f"worker_api.py not found at {WORKER_API_PATH}"


# ===========================================================================
# Section 3: JobRunner._execute_pipeline() HTTP approach
# ===========================================================================


class TestExecutePipelineHTTP:
    """Verify _execute_pipeline() uses HTTP to submit jobs and poll health."""

    @pytest.fixture(autouse=True)
    def _mock_sleep(self):
        """Mock asyncio.sleep for all pipeline tests to avoid real delays."""
        with patch("saas.workers.job_runner.asyncio.sleep", new_callable=AsyncMock):
            yield

    def _make_mock_http_client(self, health_status=200, job_response=None):
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

    @pytest.mark.asyncio
    async def test_polls_health_before_submitting(self):
        """_execute_pipeline polls /health before posting to /job."""
        mock_ctx, mock_client = self._make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
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
        mock_ctx, mock_client = self._make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(
            seed_text="Test seed material",
            goal="Research objective",
            max_rounds=42,
        )

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
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
        mock_ctx, mock_client = self._make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config()

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
            await runner._execute_pipeline("mypod-789", config)

        post_call = mock_client.post.call_args
        url = post_call[0][0] if post_call[0] else post_call.args[0]
        assert "mypod-789-5000.proxy.runpod.net" in url

    @pytest.mark.asyncio
    async def test_returns_report_and_chat_log(self):
        """Result dict has report and chat_log from the HTTP response."""
        mock_ctx, _ = self._make_mock_http_client(job_response={
            "status": "completed",
            "report": "# My Report Content",
            "chat_log": '[{"action":"comment"}]',
        })
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(job_id=99)

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
            result = await runner._execute_pipeline("pod-ret", config)

        assert result["report"] == "# My Report Content"
        assert result["chat_log"] == '[{"action":"comment"}]'

    @pytest.mark.asyncio
    async def test_returns_job_id_and_instance_id(self):
        """Result also carries job_id and instance_id for traceability."""
        mock_ctx, _ = self._make_mock_http_client()
        gpu = AsyncMock()

        runner = JobRunner(gpu_provider=gpu)
        config = _make_job_config(job_id=555)

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
            result = await runner._execute_pipeline("inst-555", config)

        assert result["job_id"] == 555
        assert result["instance_id"] == "inst-555"

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

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
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

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(TimeoutError, match="did not become ready"):
                await runner._execute_pipeline("pod-timeout", config)

    @pytest.mark.asyncio
    async def test_full_run_terminates_gpu_on_success(self):
        """runner.run() terminates the GPU instance after pipeline completes."""
        mock_ctx, _ = self._make_mock_http_client()
        gpu = AsyncMock()
        instance = _make_instance("inst-full")
        gpu.provision.return_value = instance
        gpu.terminate.return_value = None

        runner = JobRunner(gpu_provider=gpu)

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
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

        with patch("saas.workers.job_runner.httpx.AsyncClient", return_value=mock_ctx):
            with pytest.raises(TimeoutError):
                await runner.run(_make_job_config())

        gpu.terminate.assert_called_once_with("inst-fail")
