"""Tests for provisioning activities (provision_pod, wait_for_worker_health, terminate_pod)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.workflows.types import SimParams


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_provision_pod_reuses_existing_healthy_pod():
    from saas.workflows.activities.provisioning import provision_pod

    fake_resp = MagicMock(status_code=200)
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("saas.jobs.persistence._load_job_snapshot", return_value=("PROVISIONING", "pod-abc", 0)), \
         patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.workers.utils._get_gpu_provider") as mock_provider:
        pod = await provision_pod(_params(), markets=[])

    assert pod.id == "pod-abc"
    mock_provider.assert_not_called()  # did not provision a new pod


@pytest.mark.asyncio
async def test_provision_pod_creates_new_when_no_existing():
    from saas.workflows.activities.provisioning import provision_pod

    fake_instance = MagicMock(instance_id="pod-new")
    fake_provider = MagicMock()
    fake_provider.provision = AsyncMock(return_value=fake_instance)

    with patch("saas.jobs.persistence._load_job_snapshot", return_value=("PENDING", None, 0)), \
         patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider), \
         patch("saas.jobs.persistence._update_pod_id") as mock_update_pod, \
         patch("saas.jobs.persistence._update_pipeline_stage_sync") as mock_update_stage:
        pod = await provision_pod(_params(job_id=5), markets=[])

    assert pod.id == "pod-new"
    mock_update_stage.assert_called_once_with(5, 0)
    # on_created callback wires _update_pod_id; verify provider received it
    call_kwargs = fake_provider.provision.call_args.kwargs
    assert "on_created" in call_kwargs
    # trigger the on_created callback manually to verify it writes to DB
    import asyncio
    await call_kwargs["on_created"]("pod-new")
    mock_update_pod.assert_called_with(5, "pod-new")


@pytest.mark.asyncio
async def test_wait_for_worker_health_returns_on_200():
    from saas.workflows.activities.provisioning import wait_for_worker_health

    ok_resp = MagicMock(
        status_code=200,
        headers={"content-type": "application/json"},
    )
    ok_resp.json = MagicMock(return_value={"vllm_ready": True, "status": "ok"})

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=ok_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=fake_client):
        # Should return without raising
        await wait_for_worker_health("pod-xyz")

    fake_client.get.assert_called()
    # Verify it hit /health not /status
    call_url = fake_client.get.call_args[0][0]
    assert call_url.endswith("/health")


@pytest.mark.asyncio
async def test_terminate_pod_swallows_not_found():
    from saas.workflows.activities.provisioning import terminate_pod

    fake_provider = MagicMock()
    fake_provider.terminate = AsyncMock(side_effect=Exception("pod not found to terminate"))

    with patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider):
        # Must not raise
        await terminate_pod("pod-gone")

    fake_provider.terminate.assert_called_once_with("pod-gone")


@pytest.mark.asyncio
async def test_terminate_pod_calls_provider():
    from saas.workflows.activities.provisioning import terminate_pod

    fake_provider = MagicMock()
    fake_provider.terminate = AsyncMock(return_value=None)

    with patch("saas.workers.utils._get_gpu_provider", return_value=fake_provider):
        await terminate_pod("pod-alive")

    fake_provider.terminate.assert_called_once_with("pod-alive")
