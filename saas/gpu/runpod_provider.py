"""RunPod GPU provider implementation."""
from __future__ import annotations

import asyncio
import logging

import runpod  # type: ignore[import]

from saas.gpu.provider import GPUProvider, GPUProviderConfig, GPUInstance

logger = logging.getLogger(__name__)

MAX_POLL_ATTEMPTS = 120  # 120 * 5s = 10 min — the worker image now bakes in
                         # Qwen3-14B weights (see infra/docker/Dockerfile.worker),
                         # so pod readiness is gated only by RunPod's image pull
                         # + vLLM startup, not by a ~28GB HF download.


class RunPodProvider(GPUProvider):
    """GPU provider backed by RunPod on-demand pods."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        runpod.api_key = api_key

    async def provision(self, config: GPUProviderConfig, on_created=None) -> GPUInstance:
        """Create a RunPod pod, trying each supported GPU type until one has stock."""
        logger.info(f"RunPod: provisioning {config.gpu_type} with image {config.docker_image}")

        env = dict(config.env_vars or {})
        # The baked worker image ships Qwen3-14B at /models/huggingface. vLLM
        # reads HF_HOME so it loads from the image cache without re-downloading.
        env["HF_HOME"] = "/models/huggingface"
        env["TRANSFORMERS_CACHE"] = "/models/huggingface"

        # GPU types to try in order of preference. RunPod display names —
        # verified against runpod.get_gpus(). Qwen3-14B fits on 40GB+ GPUs.
        # Ordering: the tier's configured primary first, then same-class
        # alternates (H100 variants), then progressively cheaper fallbacks.
        gpu_types = [config.gpu_type,
                     "NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL",
                     "NVIDIA L40S", "NVIDIA L40", "NVIDIA A40",
                     "NVIDIA RTX A6000", "NVIDIA A100-SXM4-40GB"]
        seen = set()
        gpu_types = [g for g in gpu_types if not (g in seen or seen.add(g))]

        # Pod name encodes the job_id so cleanup_orphaned_pods can recover
        # the job binding from RunPod metadata alone, even if the DB's
        # simulation_jobs.pod_id has drifted to a different pod. Prefix
        # stays "fishcloud-sim" so the legacy name filter still matches.
        pod_name = f"fishcloud-sim-j{config.job_id}" if config.job_id else "fishcloud-sim"

        # Create without a network volume — the baked image carries the model,
        # so we can schedule on any DC (including the many non-storage ones
        # that carry most of RunPod's L40/A40/A6000 stock).
        #
        # cloud_type fallback: try the configured pool first (e.g. SECURE
        # for large tier — tight variance, ~2× hourly), then fall back to
        # ALL if every GPU type is out of stock there. Sim 152 (2026-05-17)
        # failed because SECURE L40S was empty AND we never tried community;
        # downgrading to ALL preserves the chance of running at all when
        # SECURE inventory is exhausted.
        cloud_types = [config.cloud_type]
        if config.cloud_type != "ALL":
            cloud_types.append("ALL")

        last_error = None
        pod = None
        for cloud_type in cloud_types:
            for gpu in gpu_types:
                try:
                    pod = runpod.create_pod(
                        name=pod_name,
                        image_name=config.docker_image,
                        gpu_type_id=gpu,
                        cloud_type=cloud_type,
                        gpu_count=1,
                        volume_in_gb=0,
                        # Baked image is ~42GB; allow headroom for logs/results
                        container_disk_in_gb=60,
                        ports="5000/http,8000/http",
                        env=env,
                    )
                    logger.info(
                        f"RunPod: pod created on {gpu} (cloud_type={cloud_type})")
                    break
                except Exception as e:
                    logger.warning(f"RunPod: failed {gpu}/{cloud_type}: {e}")
                    last_error = e
            if pod is not None:
                break
            if len(cloud_types) > 1 and cloud_type != cloud_types[-1]:
                logger.warning(
                    f"RunPod: {cloud_type} pool exhausted; falling back to ALL")

        if pod is None:
            raise RuntimeError(f"No RunPod GPUs available. Last: {last_error}")

        pod_id = pod["id"]
        logger.info(f"RunPod: pod {pod_id} created, waiting for it to be ready...")

        if on_created:
            try:
                await on_created(pod_id)
            except Exception as e:
                logger.warning(f"on_created callback failed: {e}")

        # Poll until running — log every 30s with elapsed time.
        # The try/except around the polling loop catches both the internal
        # timeout path AND outer cancellation (e.g. Temporal activity
        # start_to_close_timeout). Without this, CancelledError raised from
        # asyncio.sleep() would skip pod termination and leak GPU billing,
        # while the j121 tag on the orphan would veto orphan cleanup.
        import time
        start = time.monotonic()
        try:
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
        except BaseException:
            elapsed = int(time.monotonic() - start)
            try:
                runpod.terminate_pod(pod_id)
                logger.warning(
                    f"RunPod: terminated pod {pod_id} after {elapsed}s "
                    f"(provision cancelled before ready)"
                )
            except Exception as term_exc:
                logger.warning(f"RunPod: failed to terminate cancelled pod {pod_id}: {term_exc}")
            raise

        elapsed = int(time.monotonic() - start)
        try:
            runpod.terminate_pod(pod_id)
            logger.info(f"RunPod: terminated unready pod {pod_id} after {elapsed}s")
        except Exception as term_exc:
            logger.warning(f"RunPod: failed to terminate unready pod {pod_id}: {term_exc}")
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
