"""GPU provider failover logic."""
from __future__ import annotations

import logging

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

logger = logging.getLogger(__name__)


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
        except Exception as e:
            logger.warning(f"Primary GPU provider failed: {e}")

        try:
            instance = await self.fallback.provision(config)
            self._active_instances[instance.instance_id] = self.fallback
            return instance
        except Exception as e:
            logger.error(f"Fallback GPU provider also failed: {e}")
            raise RuntimeError(f"All GPU providers failed. Last error: {e}") from e

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Delegate get_status to the provider that owns the instance."""
        provider = self._active_instances.get(instance_id)
        if provider is None:
            raise KeyError(f"Unknown instance_id: {instance_id}")
        return await provider.get_status(instance_id)

    async def terminate(self, instance_id: str, provider_hint: str | None = None) -> None:
        """Delegate termination to the provider that created the instance.

        After a worker restart _active_instances is empty.  In that case
        provider_hint (e.g. "runpod" or "vastai") is used to select the
        right provider.  If neither the map nor a hint is available we
        fall back to the primary provider and log a warning.
        """
        provider = self._active_instances.get(instance_id)
        if provider is None:
            if provider_hint:
                hint_lower = provider_hint.lower()
                if "vast" in hint_lower:
                    provider = self.fallback
                else:
                    provider = self.primary
                logger.info(
                    "terminate: instance %s not in active map; using provider_hint=%r",
                    instance_id,
                    provider_hint,
                )
            else:
                logger.warning(
                    "terminate: instance %s not in active map and no provider_hint; "
                    "attempting primary provider as default",
                    instance_id,
                )
                provider = self.primary
        await provider.terminate(instance_id)
        self._active_instances.pop(instance_id, None)

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Delegate command execution to the owning provider."""
        provider = self._active_instances.get(instance_id)
        if provider is None:
            raise KeyError(f"Unknown instance_id: {instance_id}")
        return await provider.execute_command(instance_id, command)
