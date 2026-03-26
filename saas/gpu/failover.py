"""GPU provider failover logic."""
from __future__ import annotations

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance


class FailoverGPUProvider:
    """Wraps two GPU providers with automatic failover from primary to fallback."""

    def __init__(self, primary: GPUProvider, fallback: GPUProvider):
        self.primary = primary
        self.fallback = fallback
        self._active_instances: dict[str, GPUProvider] = {}

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Try primary provider first; if it fails, try fallback."""
        try:
            instance = await self.primary.provision(config)
            self._active_instances[instance.instance_id] = self.primary
            return instance
        except Exception:
            pass

        try:
            instance = await self.fallback.provision(config)
            self._active_instances[instance.instance_id] = self.fallback
            return instance
        except Exception:
            raise RuntimeError("All GPU providers failed")

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Delegate get_status to the provider that owns the instance."""
        provider = self._active_instances.get(instance_id)
        if provider is None:
            raise KeyError(f"Unknown instance_id: {instance_id}")
        return await provider.get_status(instance_id)

    async def terminate(self, instance_id: str) -> None:
        """Delegate termination to the provider that created the instance."""
        provider = self._active_instances.get(instance_id)
        if provider:
            await provider.terminate(instance_id)
            del self._active_instances[instance_id]

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Delegate command execution to the owning provider."""
        provider = self._active_instances.get(instance_id)
        if provider is None:
            raise KeyError(f"Unknown instance_id: {instance_id}")
        return await provider.execute_command(instance_id, command)
