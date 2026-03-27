"""Vast.ai GPU provider implementation."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

logger = logging.getLogger(__name__)

_VASTAI_BASE_URL = "https://console.vast.ai/api/v0"
MAX_POLL_ATTEMPTS = 60


class VastAIProvider(GPUProvider):
    """GPU provider backed by Vast.ai marketplace instances."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"Accept": "application/json"}

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Find a suitable Vast.ai offer and create an instance."""
        logger.info(f"Vast.ai: searching for {config.gpu_type}")

        # Map RunPod GPU names to Vast.ai names
        gpu_name = config.gpu_type
        if "A100" in gpu_name and "80" in gpu_name:
            gpu_name = "A100_PCIE"  # Vast.ai naming
        elif "H100" in gpu_name:
            gpu_name = "H100_SXM"

        async with httpx.AsyncClient(timeout=30) as client:
            # Vast.ai search uses a JSON-encoded query string
            query = json.dumps({
                "gpu_name": {"eq": gpu_name},
                "rentable": {"eq": True},
                "order": [["dph_total", "asc"]],
                "limit": 1,
                "type": "ask",
            })
            search_resp = await client.get(
                f"{_VASTAI_BASE_URL}/bundles/",
                params={"q": query, "api_key": self.api_key},
            )
            search_resp.raise_for_status()
            offers = search_resp.json().get("offers", [])
            if not offers:
                raise RuntimeError(f"No Vast.ai offers found for GPU: {gpu_name}")

            offer_id = offers[0]["id"]
            logger.info(f"Vast.ai: found offer {offer_id}, creating instance...")

            # Create instance
            create_resp = await client.put(
                f"{_VASTAI_BASE_URL}/asks/{offer_id}/",
                params={"api_key": self.api_key},
                json={
                    "client_id": "me",
                    "image": config.docker_image,
                    "disk": 50,
                    "env": config.env_vars or {},
                },
            )
            create_resp.raise_for_status()
            data = create_resp.json()
            instance_id = str(data.get("new_contract"))

            logger.info(f"Vast.ai: instance {instance_id} created, polling...")

            # Poll until ready
            for _ in range(MAX_POLL_ATTEMPTS):
                status = await self.get_status(instance_id)
                if status.is_ready:
                    return status
                await asyncio.sleep(5)

            raise TimeoutError(f"Vast.ai instance {instance_id} did not start")

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Fetch current instance status from Vast.ai."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_VASTAI_BASE_URL}/instances/{instance_id}/",
                params={"api_key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json().get("instances", resp.json())

        actual_status = data.get("actual_status", "")
        return GPUInstance(
            instance_id=instance_id,
            provider="vastai",
            gpu_type=data.get("gpu_name", "unknown"),
            ip_address=data.get("public_ipaddr"),
            ssh_port=data.get("ssh_port"),
            status="running" if actual_status == "running" else "provisioning",
        )

    async def terminate(self, instance_id: str) -> None:
        """Delete a Vast.ai instance."""
        logger.info(f"Vast.ai: terminating instance {instance_id}")
        async with httpx.AsyncClient(timeout=15) as client:
            await client.delete(
                f"{_VASTAI_BASE_URL}/instances/{instance_id}/",
                params={"api_key": self.api_key},
            )

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Execute via Vast.ai's SSH-based exec (requires SSH connection).
        For MVP, commands are executed via the container's entrypoint/API."""
        logger.warning("Vast.ai execute_command not fully implemented — use RunPod as primary")
        return ""
