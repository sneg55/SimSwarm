"""cloud_type wiring in RunPodProvider.provision.

Locks in two behaviors:

- Default config (no explicit cloud_type) → create_pod gets "ALL". This
  is the legacy behavior for small + medium tier sims where cost matters
  more than wall-clock variance.

- Explicit cloud_type="SECURE" on the config → create_pod gets "SECURE".
  Large-tier sims set this via TIER_CLOUD_TYPE so a single slow
  community L40S can't add hours of wall-clock (sim 147 case study:
  community host ran at 0.4 rounds/min vs the 1.0+ baseline).
"""
from unittest.mock import patch

from saas.gpu.provider import GPUProviderConfig
from saas.gpu.runpod_provider import RunPodProvider


def _config(**overrides) -> GPUProviderConfig:
    base = dict(
        gpu_type="NVIDIA L40S",
        docker_image="fake/image:tag",
        max_cost_per_hour_usd=2.0,
        timeout_seconds=3600,
        env_vars={"FOO": "bar"},
    )
    base.update(overrides)
    return GPUProviderConfig(**base)


def _ready_pod():
    return {
        "desiredStatus": "RUNNING",
        "runtime": {"ports": []},
        "machine": {"gpuDisplayName": "L40S"},
    }


async def test_provision_defaults_cloud_type_to_all():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod-default"}
        rp.get_pod.return_value = _ready_pod()

        provider = RunPodProvider("key")
        await provider.provision(_config())

        assert rp.create_pod.call_args.kwargs["cloud_type"] == "ALL"


async def test_provision_forwards_cloud_type_secure():
    with patch("saas.gpu.runpod_provider.runpod") as rp:
        rp.create_pod.return_value = {"id": "pod-secure"}
        rp.get_pod.return_value = _ready_pod()

        provider = RunPodProvider("key")
        await provider.provision(_config(cloud_type="SECURE"))

        assert rp.create_pod.call_args.kwargs["cloud_type"] == "SECURE"
