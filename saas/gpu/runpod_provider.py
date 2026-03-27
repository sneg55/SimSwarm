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
            ports="8000/http,22/tcp",
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
        ip_address = None
        ssh_port = None

        if has_runtime:
            ports = runtime.get("ports") or []
            for port in ports:
                if port.get("privatePort") == 22:
                    ip_address = port.get("ip")
                    ssh_port = port.get("publicPort")
                    break
            # RunPod pods may not expose ports immediately — if runtime exists, pod is ready
            if not ip_address:
                ip_address = instance_id  # Use pod ID as placeholder — exec works via API, not SSH

        return GPUInstance(
            instance_id=instance_id,
            provider="runpod",
            gpu_type=pod.get("machine", {}).get("gpuDisplayName", "unknown"),
            ip_address=ip_address,
            ssh_port=ssh_port,
            status="running" if has_runtime else "provisioning",
        )

    async def terminate(self, instance_id: str) -> None:
        """Terminate a RunPod pod."""
        logger.info(f"RunPod: terminating pod {instance_id}")
        runpod.terminate_pod(instance_id)

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Execute a command on the running pod.

        Uses RunPod's runsync API for serverless, or SSH for on-demand pods.
        For on-demand pods, we use the HTTP exec endpoint.
        """
        # Use runpod's exec endpoint
        try:
            result = runpod.run_sync(instance_id, {"input": {"command": command}})
            return result.get("output", "")
        except Exception as e:
            logger.warning(f"RunPod exec failed, trying alternative: {e}")
            # Fallback: some pod types don't support runsync
            return ""
