"""Tests for pod-name job tagging (2026-04-19 task-redelivery hardening PR 2)."""
from unittest.mock import AsyncMock, patch

from saas.gpu.provider import GPUProviderConfig
from saas.gpu.runpod_provider import RunPodProvider


def _config(job_id=None):
    return GPUProviderConfig(
        gpu_type="NVIDIA L40S",
        docker_image="fake/image:tag",
        max_cost_per_hour_usd=2.0,
        timeout_seconds=3600,
        env_vars={},
        job_id=job_id,
    )


async def test_pod_name_encodes_job_id_when_set():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "p"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }
        provider = RunPodProvider("k")
        await provider.provision(_config(job_id=119), on_created=AsyncMock())

        assert rp.create_pod.call_args.kwargs["name"] == "fishcloud-sim-j119"


async def test_pod_name_stays_legacy_when_job_id_is_none():
    """Backwards compat: callers that don't pass job_id (legacy tests, any
    non-Celery code) get the unchanged legacy name."""
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "p"}
        rp.get_pod.return_value = {
            "desiredStatus": "RUNNING",
            "runtime": {"ports": []},
            "machine": {"gpuDisplayName": "L40S"},
        }
        provider = RunPodProvider("k")
        await provider.provision(_config(job_id=None), on_created=AsyncMock())

        assert rp.create_pod.call_args.kwargs["name"] == "fishcloud-sim"
