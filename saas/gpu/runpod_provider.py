"""RunPod GPU provider implementation."""
from __future__ import annotations

import asyncio
import logging

import runpod  # type: ignore[import]

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

logger = logging.getLogger(__name__)

MAX_POLL_ATTEMPTS = 120  # 120 * 5s = 10 min max wait for image pull


class RunPodProvider(GPUProvider):
    """GPU provider backed by RunPod on-demand pods."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        runpod.api_key = api_key

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Create a RunPod pod with the given configuration."""
        logger.info(f"RunPod: provisioning {config.gpu_type} with image {config.docker_image}")

        pod = runpod.create_pod(
            name="fishcloud-sim",
            image_name=config.docker_image,
            gpu_type_id=config.gpu_type,
            cloud_type="ALL",
            gpu_count=1,
            volume_in_gb=0,
            container_disk_in_gb=100,
            ports="5000/http,8000/http",
            env=config.env_vars or {},
        )

        pod_id = pod["id"]
        logger.info(f"RunPod: pod {pod_id} created, waiting for it to be ready...")

        # Poll until running
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                status = await self.get_status(pod_id)
                if status.is_ready:
                    logger.info(f"RunPod: pod {pod_id} is ready at {status.ip_address}")
                    return status
                if attempt % 12 == 0:
                    logger.info(f"RunPod: pod {pod_id} still provisioning... (attempt {attempt + 1})")
            except Exception as e:
                logger.warning(f"RunPod: poll error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(5)

        raise TimeoutError(f"RunPod pod {pod_id} did not become ready in {MAX_POLL_ATTEMPTS * 5}s")

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Fetch current pod status from RunPod."""
        pod = runpod.get_pod(instance_id)
        raw_status = (pod.get("desiredStatus") or "").upper()
        runtime = pod.get("runtime") or {}

        has_runtime = raw_status == "RUNNING" and bool(runtime)

        # RunPod HTTP proxy URL for the worker API on port 5000.
        # Format: https://{pod_id}-5000.proxy.runpod.net
        # Set ip_address to the proxy URL so callers can reach the worker API.
        ip_address = None
        if has_runtime:
            ip_address = f"https://{instance_id}-5000.proxy.runpod.net"

        return GPUInstance(
            instance_id=instance_id,
            provider="runpod",
            gpu_type=pod.get("machine", {}).get("gpuDisplayName", "unknown"),
            ip_address=ip_address,
            ssh_port=None,
            status="running" if has_runtime else "provisioning",
        )

    async def terminate(self, instance_id: str) -> None:
        """Terminate a RunPod pod."""
        logger.info(f"RunPod: terminating pod {instance_id}")
        runpod.terminate_pod(instance_id)

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Not used with HTTP approach — kept for interface compatibility."""
        return ""

    async def submit_job(self, instance_id: str, seed_text: str, goal: str, max_rounds: int) -> dict:
        """Submit a job to the worker API via HTTP."""
        import httpx
        url = f"https://{instance_id}-5000.proxy.runpod.net/job"
        async with httpx.AsyncClient(timeout=3600) as client:
            resp = await client.post(url, json={
                "seed_text": seed_text,
                "goal": goal,
                "max_rounds": max_rounds,
            })
            resp.raise_for_status()
            return resp.json()
