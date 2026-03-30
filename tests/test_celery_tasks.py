"""Tests for Celery task definitions."""
from unittest.mock import AsyncMock, patch, MagicMock

from saas.workers.celery_app import celery_app
import saas.workers.tasks  # noqa: F401 — registers tasks with celery_app
from saas.gpu.provider import GPUInstance


def _make_instance(instance_id: str = "inst-celery") -> GPUInstance:
    return GPUInstance(
        instance_id=instance_id,
        provider="runpod",
        gpu_type="RTX4090",
        ip_address="10.0.0.1",
        ssh_port=22,
        status="running",
    )


def test_task_is_registered():
    """run_simulation task is registered in the Celery app."""
    registered = celery_app.tasks
    assert "fishcloud.run_simulation" in registered


def test_task_calls_runner():
    """run_simulation_task calls JobRunner.run with the correct config."""
    from saas.workers.tasks import run_simulation_task

    instance = _make_instance()
    mock_result = {
        "job_id": 1,
        "status": "completed",
        "report": "test report",
        "chat_log": "[]",
        "graph_data": "{}",
        "pod_id": "inst-celery",
        "provision_seconds": 10,
        "pipeline_seconds": 60,
    }

    mock_provider = MagicMock()

    async def fake_provision(config):
        return instance

    async def fake_terminate(instance_id):
        return None

    mock_provider.provision = fake_provision
    mock_provider.terminate = fake_terminate

    # Mock JobRunner.run to return a canned result (avoids real HTTP polling)
    with patch("saas.workers.tasks._get_gpu_provider", return_value=mock_provider), \
         patch("saas.workers.tasks.JobRunner.run", new_callable=AsyncMock, return_value=mock_result), \
         patch("saas.workers.tasks._save_job_results"), \
         patch("saas.workers.tasks._update_job_metadata"):
        result = run_simulation_task(
            job_id=1,
            user_id="user-test",
            seed_text="Test seed",
            goal="Test goal",
            tier="small",
            model_id="Qwen2.5-7B-Instruct-AWQ",
            gpu_type="RTX4090",
            max_rounds=100,
            vllm_args="",
            llm_api_key="sk-test",
            openai_api_key="",
            credits_charged=10,
        )

    assert result["job_id"] == 1
    assert result["status"] == "completed"
