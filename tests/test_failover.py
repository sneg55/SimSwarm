"""Tests for GPU provider failover logic."""
import pytest
from unittest.mock import AsyncMock

from saas.gpu.provider import GPUProviderConfig, GPUInstance
from saas.gpu.failover import FailoverGPUProvider


def _make_instance(instance_id: str, provider: str = "runpod") -> GPUInstance:
    return GPUInstance(
        instance_id=instance_id,
        provider=provider,
        gpu_type="RTX4090",
        ip_address="10.0.0.1",
        ssh_port=22,
        status="running",
    )


def _make_config() -> GPUProviderConfig:
    return GPUProviderConfig(
        gpu_type="RTX4090",
        docker_image="mirofish:latest",
        max_cost_per_hour_usd=2.50,
        timeout_seconds=3600,
    )


@pytest.mark.asyncio
async def test_primary_succeeds_no_failover():
    """When primary succeeds, fallback is never called."""
    primary = AsyncMock()
    fallback = AsyncMock()

    expected = _make_instance("inst-primary", "runpod")
    primary.provision.return_value = expected

    fp = FailoverGPUProvider(primary=primary, fallback=fallback)
    result = await fp.provision(_make_config())

    assert result.instance_id == "inst-primary"
    primary.provision.assert_called_once()
    fallback.provision.assert_not_called()


@pytest.mark.asyncio
async def test_failover_to_secondary_when_primary_fails():
    """When primary raises, fallback is used."""
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.provision.side_effect = RuntimeError("RunPod unavailable")
    expected = _make_instance("inst-fallback", "vastai")
    fallback.provision.return_value = expected

    fp = FailoverGPUProvider(primary=primary, fallback=fallback)
    result = await fp.provision(_make_config())

    assert result.instance_id == "inst-fallback"
    assert result.provider == "vastai"
    primary.provision.assert_called_once()
    fallback.provision.assert_called_once()


@pytest.mark.asyncio
async def test_both_fail_raises_runtime_error():
    """When both providers fail, RuntimeError is raised."""
    primary = AsyncMock()
    fallback = AsyncMock()

    primary.provision.side_effect = RuntimeError("RunPod down")
    fallback.provision.side_effect = RuntimeError("Vast.ai down")

    fp = FailoverGPUProvider(primary=primary, fallback=fallback)
    with pytest.raises(RuntimeError, match="All GPU providers failed"):
        await fp.provision(_make_config())


@pytest.mark.asyncio
async def test_terminate_delegates_to_correct_provider():
    """Terminate delegates to the provider that created the instance."""
    primary = AsyncMock()
    fallback = AsyncMock()

    instance = _make_instance("inst-xyz", "runpod")
    primary.provision.return_value = instance

    fp = FailoverGPUProvider(primary=primary, fallback=fallback)
    await fp.provision(_make_config())
    await fp.terminate("inst-xyz")

    primary.terminate.assert_called_once_with("inst-xyz")
    fallback.terminate.assert_not_called()
    assert "inst-xyz" not in fp._active_instances
