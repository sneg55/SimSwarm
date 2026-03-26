"""RunPod GPU provider implementation."""
from __future__ import annotations

import runpod  # type: ignore[import]

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance


class RunPodProvider(GPUProvider):
    """GPU provider backed by RunPod serverless / on-demand pods."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        runpod.api_key = api_key

    async def provision(self, config: GPUProviderConfig) -> GPUInstance:
        """Create a RunPod pod with the given configuration."""
        pod = runpod.create_pod(
            name="fishcloud-sim",
            image_name=config.docker_image,
            gpu_type_id=config.gpu_type,
            cloud_type="SECURE",
            env=config.env_vars or {},
        )
        return GPUInstance(
            instance_id=pod["id"],
            provider="runpod",
            gpu_type=config.gpu_type,
            ip_address=pod.get("desiredStatus") and pod.get("runtime", {}).get("uptimeInSeconds") and None,
            ssh_port=None,
            status="provisioning",
        )

    async def get_status(self, instance_id: str) -> GPUInstance:
        """Fetch current pod status from RunPod."""
        pod = runpod.get_pod(instance_id)
        raw_status = pod.get("desiredStatus", "").lower()
        status_map = {
            "running": "running",
            "exited": "stopped",
            "failed": "error",
        }
        status = status_map.get(raw_status, "provisioning")
        runtime = pod.get("runtime") or {}
        ports = runtime.get("ports") or []
        ip_address = None
        ssh_port = None
        for port in ports:
            if port.get("privatePort") == 22:
                ip_address = port.get("ip")
                ssh_port = port.get("publicPort")
                break
        return GPUInstance(
            instance_id=instance_id,
            provider="runpod",
            gpu_type=pod.get("machine", {}).get("gpuDisplayName", "unknown"),
            ip_address=ip_address,
            ssh_port=ssh_port,
            status=status,
        )

    async def terminate(self, instance_id: str) -> None:
        """Terminate a RunPod pod."""
        runpod.terminate_pod(instance_id)

    async def execute_command(self, instance_id: str, command: str) -> str:
        """Execute a command on the running pod via RunPod exec API."""
        result = runpod.run_sync(instance_id, {"input": {"command": command}})
        return result.get("output", "")
