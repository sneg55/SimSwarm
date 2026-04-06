"""
Tests for worker_api.py Flask endpoints.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKER_API_PATH = Path(__file__).parent.parent / "infra" / "docker" / "worker_api.py"


# ===========================================================================
# Tests
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
