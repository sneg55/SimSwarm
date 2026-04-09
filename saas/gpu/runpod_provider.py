"""RunPod GPU provider implementation."""
from __future__ import annotations

import asyncio
import logging

import runpod  # type: ignore[import]

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

logger = logging.getLogger(__name__)

MAX_POLL_ATTEMPTS = 120  # 120 * 5s = 10 min max wait for image pull

# Network volumes with pre-loaded model weights across datacenters.
# The provider tries each volume until it finds one with GPU availability.
NETWORK_VOLUMES = [
    {"id": "19hqjpxbp2", "dc": "US-TX-3"},   # 50GB, Qwen3-14B cached on first use
    {"id": "8aplig09qc", "dc": "EU-RO-1"},   # 50GB, Qwen3-14B cached on first use
]


class RunPodProvider(GPUProvider):
    """GPU provider backed by RunPod on-demand pods."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        runpod.api_key = api_key

    async def provision(self, config: GPUProviderConfig, on_created=None) -> GPUInstance:
        """Create a RunPod pod, trying multiple datacenter volumes for availability."""
        logger.info(f"RunPod: provisioning {config.gpu_type} with image {config.docker_image}")

        env = dict(config.env_vars or {})
        env["HF_HOME"] = "/models/huggingface"
        env["TRANSFORMERS_CACHE"] = "/models/huggingface"

        # GPU types to try in order of preference
        # Qwen3-14B needs ~28GB VRAM (weights + KV cache), fits on 40GB+ GPUs
        # L40S (48GB) is the sweet spot for price/performance
        gpu_types = [config.gpu_type, "NVIDIA L40S", "NVIDIA A40", "NVIDIA RTX A6000", "NVIDIA A100 40GB"]
        # Deduplicate while preserving order
        seen = set()
        gpu_types = [g for g in gpu_types if not (g in seen or seen.add(g))]

        # Try each volume+GPU combo, then try without volume as last resort
        last_error = None
        volume_configs = [*[{"id": v["id"], "dc": v["dc"]} for v in NETWORK_VOLUMES], None]

        for vol in volume_configs:
            for gpu in gpu_types:
                try:
                    kwargs = dict(
                        name="fishcloud-sim",
                        image_name=config.docker_image,
                        gpu_type_id=gpu,
                        cloud_type="ALL",
                        gpu_count=1,
                        volume_in_gb=0,
                        container_disk_in_gb=30 if vol is None else 15,
                        ports="5000/http,8000/http",
                        env=env,
                    )
                    if vol:
                        kwargs["network_volume_id"] = vol["id"]
                        kwargs["volume_mount_path"] = "/models"
                    pod = runpod.create_pod(**kwargs)
                    dc_label = vol["dc"] if vol else "any (no volume)"
                    logger.info(f"RunPod: pod created on {gpu} in {dc_label}")
                    break
                except Exception as e:
                    dc = vol["dc"] if vol else "no-volume"
                    logger.warning(f"RunPod: failed {gpu} in {dc}: {e}")
                    last_error = e
                    continue
            else:
                continue
            break
        else:
            raise RuntimeError(f"No RunPod GPUs available. Last: {last_error}")

        pod_id = pod["id"]
        logger.info(f"RunPod: pod {pod_id} created, waiting for it to be ready...")

        if on_created:
            try:
                await on_created(pod_id)
            except Exception as e:
                logger.warning(f"on_created callback failed: {e}")

        # Poll until running — log every 30s with elapsed time
        import time
        start = time.monotonic()
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                status = await self.get_status(pod_id)
                if status.is_ready:
                    elapsed = int(time.monotonic() - start)
                    logger.info(f"RunPod: pod {pod_id} ready in {elapsed}s at {status.ip_address}")
                    return status
                if attempt % 6 == 0:  # every 30s
                    elapsed = int(time.monotonic() - start)
                    logger.info(f"RunPod: pod {pod_id} provisioning... ({elapsed}s elapsed, attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})")
            except Exception as e:
                logger.warning(f"RunPod: poll error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(5)

        elapsed = int(time.monotonic() - start)
        raise TimeoutError(f"RunPod pod {pod_id} did not become ready after {elapsed}s ({MAX_POLL_ATTEMPTS} attempts)")

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
