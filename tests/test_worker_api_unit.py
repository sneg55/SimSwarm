"""
Unit tests for the GPU worker Flask API (worker_api.py).

Covers additional edge cases not already tested in test_gpu_worker.py:
  - /health returns 503 when vLLM is not running
  - /job rejects a second submission when one is already running (409)
  - /logs returns empty when no job has run
  - /status returns idle on a fresh worker
  - /status includes result payload when job is completed
  - /status includes error when job has failed
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

WORKER_API_PATH = Path(__file__).parent.parent / "infra" / "docker" / "worker_api.py"


def _load_worker_api():
    """Load worker_api module fresh each time to get a clean job state."""
    spec = importlib.util.spec_from_file_location("worker_api_fresh", WORKER_API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Reset job state to idle
    mod._job["status"] = "idle"
    mod._job["result"] = None
    mod._job["error"] = None
    mod.app.config["TESTING"] = True
    return mod


@pytest.fixture()
def worker_client():
    """Yield (flask_test_client, module) with fresh idle state."""
    mod = _load_worker_api()
    return mod.app.test_client(), mod


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestWorkerHealthEndpoint:
    def test_health_returns_503_when_vllm_not_running(self, worker_client):
        """When vLLM is unreachable /health returns 503 with waiting_for_vllm."""
        flask_client, _ = worker_client
        with patch("requests.get", side_effect=ConnectionError("vLLM down")):
            resp = flask_client.get("/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["vllm_ready"] is False
        assert data["status"] == "waiting_for_vllm"

    def test_health_returns_200_when_vllm_ready(self, worker_client):
        """When vLLM responds 200 /health returns 200 ok."""
        flask_client, _ = worker_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("requests.get", return_value=mock_response):
            resp = flask_client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["vllm_ready"] is True
        assert data["status"] == "ok"

    def test_health_reports_current_job_status(self, worker_client):
        """job_status field in health reflects the current _job state."""
        flask_client, mod = worker_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("requests.get", return_value=mock_response):
            resp = flask_client.get("/health")
        assert resp.get_json()["job_status"] == "idle"

        mod._job["status"] = "running"
        with patch("requests.get", return_value=mock_response):
            resp = flask_client.get("/health")
        assert resp.get_json()["job_status"] == "running"


# ---------------------------------------------------------------------------
# /job
# ---------------------------------------------------------------------------


class TestWorkerJobEndpoint:
    def test_job_rejects_when_already_running(self, worker_client):
        """POST /job returns 409 when a job is already in running state."""
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.post(
            "/job",
            json={"seed_text": "text", "goal": "goal", "max_rounds": 10},
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "already running" in data["error"]

    def test_job_accepted_when_idle(self, worker_client):
        """POST /job returns 200 accepted when worker is idle."""
        flask_client, mod = worker_client
        # Patch threading.Thread so pipeline doesn't actually run
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            with patch("pathlib.Path.write_text"):
                resp = flask_client.post(
                    "/job",
                    json={"seed_text": "Some seed text", "goal": "Some goal", "max_rounds": 50},
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "accepted"

    def test_job_accepted_after_previous_completed(self, worker_client):
        """A new job can be submitted after a previous one completed."""
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {"chat_log": "[]"}
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            with patch("pathlib.Path.write_text"):
                resp = flask_client.post(
                    "/job",
                    json={"seed_text": "New seed", "goal": "New goal", "max_rounds": 10},
                )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "accepted"


# ---------------------------------------------------------------------------
# /logs
# ---------------------------------------------------------------------------


class TestWorkerLogsEndpoint:
    def test_logs_returns_empty_when_no_job_run(self, worker_client):
        """GET /logs returns empty lines list when log file does not exist."""
        flask_client, _ = worker_client
        with patch("pathlib.Path.exists", return_value=False):
            resp = flask_client.get("/logs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["lines"] == []
        assert data["total_lines"] == 0

    def test_logs_returns_pipeline_lines(self, worker_client):
        """GET /logs?source=pipeline returns pipeline log lines prefixed [pipeline]."""
        flask_client, _ = worker_client
        fake_log = "Step 1 done\nStep 2 done\nStep 3 done"

        def fake_exists(self):
            return str(self).endswith("pipeline.log")

        with patch("pathlib.Path.exists", fake_exists), \
             patch("pathlib.Path.read_text", return_value=fake_log):
            resp = flask_client.get("/logs?source=pipeline")

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["lines"]) == 3
        assert all(line.startswith("[pipeline]") for line in data["lines"])

    def test_logs_tail_parameter_limits_output(self, worker_client):
        """The tail query parameter caps the number of lines returned."""
        flask_client, _ = worker_client
        # Generate 20 lines
        fake_log = "\n".join(f"Line {i}" for i in range(20))

        def fake_exists(self):
            return str(self).endswith("pipeline.log")

        with patch("pathlib.Path.exists", fake_exists), \
             patch("pathlib.Path.read_text", return_value=fake_log):
            resp = flask_client.get("/logs?source=pipeline&tail=5")

        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["lines"]) == 5

    def test_logs_includes_job_status(self, worker_client):
        """GET /logs always includes the current job_status field."""
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        with patch("pathlib.Path.exists", return_value=False):
            resp = flask_client.get("/logs")
        assert resp.get_json()["job_status"] == "running"


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------


class TestWorkerStatusEndpoint:
    def test_status_returns_idle_initially(self, worker_client):
        """GET /status returns idle on a fresh worker."""
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_status_returns_running_during_job(self, worker_client):
        """GET /status reflects running state while a job is in progress."""
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "running"

    def test_status_includes_result_when_completed(self, worker_client):
        """GET /status includes chat_log (but not report) when status is completed.

        report is no longer produced by the pod — it is generated by the
        external-LLM Celery task (saas/jobs/tasks_report.py).
        """
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {
            "chat_log": '[{"action": "post"}]',
        }
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "completed"
        assert "report" not in data
        assert data["chat_log"] == '[{"action": "post"}]'

    def test_status_includes_error_when_failed(self, worker_client):
        """GET /status includes error field when job has failed."""
        flask_client, mod = worker_client
        mod._job["status"] = "failed"
        mod._job["error"] = "Fatal error: out of memory"
        resp = flask_client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "failed"
        assert data["error"] == "Fatal error: out of memory"

    def test_status_no_result_field_when_idle(self, worker_client):
        """GET /status does not include chat_log key when idle."""
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert "report" not in data  # never present (report moved to Celery worker)
        assert "chat_log" not in data
