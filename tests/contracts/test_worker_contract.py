"""Contract tests for the worker API HTTP interface.

Tests that /health, /job, and /status endpoints return the exact shapes
that JobRunner expects. Both MiroShark and SimSwarm workers must pass.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

WORKER_API_PATH = Path(__file__).resolve().parent.parent.parent / "infra" / "docker" / "worker_api.py"


@pytest.fixture()
def worker_client():
    """Load fresh worker_api module and return Flask test client."""
    spec = importlib.util.spec_from_file_location("worker_api_contract", WORKER_API_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._job["status"] = "idle"
    mod._job["result"] = None
    mod._job["error"] = None
    mod.app.config["TESTING"] = True
    return mod.app.test_client(), mod


class TestHealthContract:
    """GET /health must return {status, vllm_ready, job_status}."""

    def test_health_shape_when_vllm_ready(self, worker_client):
        flask_client, _ = worker_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "model"}]}
        with patch("requests.get", return_value=mock_resp):
            resp = flask_client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data
        assert "vllm_ready" in data
        assert "job_status" in data
        assert data["status"] == "ok"
        assert data["vllm_ready"] is True

    def test_health_shape_when_vllm_down(self, worker_client):
        flask_client, _ = worker_client
        with patch("requests.get", side_effect=ConnectionError("down")):
            resp = flask_client.get("/health")
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "waiting_for_vllm"
        assert data["vllm_ready"] is False

    def test_health_includes_job_status(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        with patch("requests.get", side_effect=ConnectionError()):
            resp = flask_client.get("/health")
        data = resp.get_json()
        assert data["job_status"] == "running"


class TestJobSubmitContract:
    """POST /job must accept {seed_text, goal, max_rounds} and return {status}."""

    def test_accepts_required_fields(self, worker_client):
        flask_client, mod = worker_client
        with patch("threading.Thread") as mock_thread_cls, \
             patch("pathlib.Path.write_text"):
            mock_thread_cls.return_value = MagicMock()
            resp = flask_client.post(
                "/job",
                json={
                    "seed_text": "Test seed about AI policy",
                    "goal": "Predict policy outcomes",
                    "max_rounds": 15,
                },
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "accepted"

    def test_accepts_optional_fields(self, worker_client):
        flask_client, mod = worker_client
        with patch("threading.Thread") as mock_thread_cls, \
             patch("pathlib.Path.write_text"):
            mock_thread_cls.return_value = MagicMock()
            resp = flask_client.post(
                "/job",
                json={
                    "seed_text": "Test seed",
                    "goal": "Test goal",
                    "max_rounds": 10,
                    "forecast_days": 7,
                    "target_agents": 10,
                    "upload_urls": {"posts": "https://example.com/upload"},
                },
                content_type="application/json",
            )
        assert resp.status_code == 200

    def test_rejects_when_already_running(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.post(
            "/job",
            json={"seed_text": "x", "goal": "y", "max_rounds": 5},
            content_type="application/json",
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data


class TestStatusContract:
    """GET /status must return {status} and result fields when completed."""

    def test_idle_status_shape(self, worker_client):
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_completed_status_has_all_result_fields(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {
            "report": "# Test Report\n\nFindings here.",
            "chat_log": json.dumps([{"agent_name": "A", "action_type": "CREATE_POST",
                                     "round_num": 1, "platform": "twitter",
                                     "agent_id": 1, "action_args": {}}]),
            "graph_data": json.dumps({
                "nodes": [{"uuid": "n1", "name": "X", "labels": ["Entity"], "summary": "s"}],
                "edges": [],
                "metadata": {"entity_types": ["Entity"], "total_nodes": 1, "total_edges": 0},
            }),
            "structured": json.dumps({
                "brief": "Test", "findings": [], "sentiment": [],
                "coalitions": [], "confidence": [],
            }),
        }
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "completed"
        assert "report" in data
        assert "chat_log" in data
        assert "graph_data" in data
        assert "structured" in data

    def test_completed_result_fields_are_strings(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "completed"
        mod._job["result"] = {
            "report": "# Report",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
        }
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert isinstance(data["report"], str)
        assert isinstance(data["chat_log"], str)
        assert isinstance(data["graph_data"], str)
        assert isinstance(data["structured"], str)

    def test_failed_status_has_error(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "failed"
        mod._job["error"] = "GPU OOM"
        resp = flask_client.get("/status")
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "error" in data


class TestStatusValues:
    """Status field must only contain values JobRunner knows how to handle."""

    VALID_STATUSES = {"idle", "running", "completed", "failed"}

    def test_idle_is_valid(self, worker_client):
        flask_client, _ = worker_client
        resp = flask_client.get("/status")
        assert resp.get_json()["status"] in self.VALID_STATUSES

    def test_running_is_valid(self, worker_client):
        flask_client, mod = worker_client
        mod._job["status"] = "running"
        resp = flask_client.get("/status")
        assert resp.get_json()["status"] in self.VALID_STATUSES
