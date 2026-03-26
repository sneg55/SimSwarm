"""Vast.ai GPU provider implementation."""
from __future__ import annotations

import httpx

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

_VASTAI_BASE_URL = "https://console.vast.ai/api/v0"


class VastAIProvider(GPUProvider):
    """GPU provider backed by Vast.ai marketplace instances."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Find a suitable Vast.ai offer and create an instance."""
        async with httpx.AsyncClient() as client:
            # Search for offers matching the GPU type
            search_resp = await client.get(
                f"{_VASTAI_BASE_URL}/bundles/",
                headers=self._headers,
                params={
                    "q": {
                        "gpu_name": {"eq": config.gpu_type},
                        "rentable": {"eq": True},
                        "order": [["dph_total", "asc"]],
                        "limit": 1,
                    }
                },
            )
            search_resp.raise_for_status()
            offers = search_resp.json().get("offers", [])
            if not offers:
                raise RuntimeError(f"No Vast.ai offers found for GPU type: {config.gpu_type}")

            offer_id = offers[0]["id"]

            # Create instance from the offer
            env_str = " ".join(f"-e {k}={v}" for k, v in (config.env_vars or {}).items())
            create_resp = await client.put(
                f"{_VASTAI_BASE_URL}/asks/{offer_id}/",
                headers=self._headers,
                json={
                    "client_id": "me",
                    "image": config.docker_image,
                    "runtype": "ssh",
                    "disk": 20,
                    "onstart": f"docker run {env_str} {config.docker_image}",
                },
            )
            create_resp.raise_for_status()
            data = create_resp.json()
            instance_id = str(data.get("new_contract"))

        return GPUInstance(
            instance_id=instance_id,
            provider="vastai",
            gpu_type=config.gpu_type,
            ip_address=None,
            ssh_port=None,
            status="provisioning",
        )

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Fetch current instance status from Vast.ai."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_VASTAI_BASE_URL}/instances/{instance_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json().get("instances", {})

        actual_status = data.get("actual_status", "")
        status_map = {
            "running": "running",
            "exited": "stopped",
            "failed": "error",
        }
        status = status_map.get(actual_status, "provisioning")
        return GPUInstance(
            instance_id=instance_id,
            provider="vastai",
            gpu_type=data.get("gpu_name", "unknown"),
            ip_address=data.get("public_ipaddr"),
            ssh_port=data.get("ssh_port"),
            status=status,
        )

    async def terminate(self, instance_id: str) -> None:
        """Delete a Vast.ai instance."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{_VASTAI_BASE_URL}/instances/{instance_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Execute a command on the running instance via SSH tunnel proxy."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_VASTAI_BASE_URL}/instances/{instance_id}/",
                headers=self._headers,
                json={"command": command},
            )
            resp.raise_for_status()
            return resp.json().get("output", "")
