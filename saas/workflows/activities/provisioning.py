"""Provisioning-phase activities: pod creation, health wait, teardown."""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from saas.workflows.types import PodInfo, SimParams

logger = logging.getLogger(__name__)

# Strings in the worker's /logs output that mean vLLM will never come up on
# this pod. Seeing one of these is a terminal signal: we should abort the
# sim immediately rather than keep polling /health for the full timeout.
_VLLM_TERMINAL_ERRORS = (
    "CUDA driver initialization failed",
    "Engine core initialization failed",
    "no CUDA-capable device",
    "Failed to initialize NCCL",
)


async def _heartbeat_every(interval_s: float) -> None:
    """Background task that pings Temporal heartbeat on a fixed interval."""
    try:
        while True:
            if activity.in_activity():
                activity.heartbeat()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        return


@activity.defn(name="fishcloud.provision_pod")
async def provision_pod(params: SimParams, markets: list[dict]) -> PodInfo:
    """Provision a RunPod instance. Idempotent on re-entry: if an existing pod
    for this job_id is healthy, reuse it instead of creating a new one.
    """
    from saas.jobs.persistence import (
        _load_job_snapshot,
        _update_pipeline_stage_sync,
        _update_pod_id,
    )
    from saas.workers.utils import _get_gpu_provider

    # Idempotent re-entry check: if a pod already exists and is healthy, reuse
    snapshot = _load_job_snapshot(params.job_id)
    if snapshot is not None:
        _status, existing_pod_id, _retry = snapshot
        if existing_pod_id:
            existing_is_healthy = False
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    url = f"https://{existing_pod_id}-5000.proxy.runpod.net/health"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        existing_is_healthy = True
            except Exception as e:
                logger.info(
                    "activity.provision_pod.existing_unhealthy "
                    "job_id=%d pod_id=%s error=%s",
                    params.job_id, existing_pod_id, e,
                )

            if existing_is_healthy:
                logger.info(
                    "activity.provision_pod.reuse job_id=%d pod_id=%s",
                    params.job_id, existing_pod_id,
                )
                return PodInfo(id=existing_pod_id)

            # Unhealthy pod on re-entry: terminate before creating fresh.
            # Otherwise the old pod keeps running (cleanup vetoes it because
            # its job_id tag still matches a live job) and we leak GPU cost.
            try:
                await _get_gpu_provider().terminate(existing_pod_id)
                logger.warning(
                    "activity.provision_pod.terminated_stale "
                    "job_id=%d pod_id=%s",
                    params.job_id, existing_pod_id,
                )
            except Exception as term_exc:
                logger.warning(
                    "activity.provision_pod.terminate_stale_failed "
                    "job_id=%d pod_id=%s error=%s",
                    params.job_id, existing_pod_id, term_exc,
                )

    _update_pipeline_stage_sync(params.job_id, 0)

    from saas.constants.tiers import TIER_CLOUD_TYPE, TIER_MAX_COST_USD, TIER_TIMEOUTS
    from saas.gpu.provider import GPUProviderConfig
    from saas.jobs.config import JobConfig, get_worker_image

    job_config = JobConfig(
        job_id=params.job_id,
        user_id=params.user_id,
        seed_text=params.seed_text,
        goal=params.goal,
        tier=params.tier,
        model_id=params.model_id,
        gpu_type=params.gpu_type,
        max_rounds=params.max_rounds,
        vllm_args=params.vllm_args,
        llm_api_key=params.llm_api_key,
        openai_api_key=params.openai_api_key,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        forecast_days=params.forecast_days,
        target_agents=params.target_agents,
        upload_urls=params.upload_urls,
        markets_config=markets,
    )

    gpu_config = GPUProviderConfig(
        gpu_type=params.gpu_type,
        docker_image=get_worker_image(),
        max_cost_per_hour_usd=TIER_MAX_COST_USD.get(params.tier, 4.00),
        timeout_seconds=TIER_TIMEOUTS.get(params.tier, 2700),
        env_vars=job_config.to_worker_env(),
        job_id=params.job_id,
        cloud_type=TIER_CLOUD_TYPE.get(params.tier, "ALL"),
    )

    async def _on_created(pid: str) -> None:
        _update_pod_id(params.job_id, pid)
        if activity.in_activity():
            activity.heartbeat()

    heartbeat_task = asyncio.create_task(_heartbeat_every(30))
    try:
        gpu_provider = _get_gpu_provider()
        instance = await gpu_provider.provision(gpu_config, on_created=_on_created)
        return PodInfo(id=instance.instance_id)
    finally:
        heartbeat_task.cancel()


async def _check_vllm_terminal_failure(
    client: httpx.AsyncClient, worker_url: str, pod_id: str,
) -> str | None:
    """Fetch the worker's /logs and scan for terminal vLLM errors.

    Returns the matching error string if found, None otherwise. The worker
    exposes its stdout/stderr tail at /logs, so this lets us detect a dead
    GPU driver or failed engine start without waiting out the whole timeout.
    """
    try:
        resp = await client.get(f"{worker_url}/logs", timeout=10)
        if resp.status_code != 200:
            return None
        body = resp.json() if resp.headers.get(
            "content-type", "").startswith("application/json") else {}
        for line in body.get("lines", []):
            for marker in _VLLM_TERMINAL_ERRORS:
                if marker in line:
                    return marker
    except Exception as e:
        logger.debug(
            "wait_for_worker_health.logs_probe_failed pod_id=%s error=%s",
            pod_id, type(e).__name__,
        )
    return None


@activity.defn(name="fishcloud.wait_for_worker_health")
async def wait_for_worker_health(pod_id: str) -> None:
    """Poll /health until 200 OK. Heartbeats on each attempt.

    Every ~30s we also scan /logs for terminal vLLM errors (bad GPU driver,
    failed NCCL init, engine core failure). Seeing one of those aborts the
    wait with a non-retryable error, so the workflow can move on to refund
    and teardown instead of burning the full 15-min timeout window.
    """
    worker_url = f"https://{pod_id}-5000.proxy.runpod.net"
    poll_count = 0
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            if activity.in_activity():
                activity.heartbeat()
            try:
                resp = await client.get(f"{worker_url}/health", timeout=10)
                if resp.status_code == 200:
                    body = resp.json() if resp.headers.get(
                        "content-type", "").startswith("application/json") else {}
                    logger.info(
                        "activity.wait_for_worker_health.ready pod_id=%s vllm_ready=%s",
                        pod_id, body.get("vllm_ready", "?"),
                    )
                    return
            except httpx.ConnectError:
                pass
            except Exception as e:
                logger.info(
                    "activity.wait_for_worker_health.retry pod_id=%s error=%s",
                    pod_id, type(e).__name__,
                )

            poll_count += 1
            # Probe /logs every ~30s (every 6 polls at 5s spacing). Earlier
            # polls are wasted because the worker hasn't written its stdout
            # tail yet; later polls are cheap compared to the 15-min budget.
            if poll_count >= 6 and poll_count % 6 == 0:
                marker = await _check_vllm_terminal_failure(client, worker_url, pod_id)
                if marker is not None:
                    logger.warning(
                        "activity.wait_for_worker_health.vllm_terminal "
                        "pod_id=%s marker=%r",
                        pod_id, marker,
                    )
                    raise ApplicationError(
                        f"vLLM failed to start on pod {pod_id}: {marker}",
                        non_retryable=True,
                    )

            await asyncio.sleep(5)


@activity.defn(name="fishcloud.terminate_pod")
async def terminate_pod(pod_id: str) -> None:
    """Terminate the pod. Idempotent — swallows 'not found' errors."""
    from saas.workers.utils import _get_gpu_provider

    gpu_provider = _get_gpu_provider()
    try:
        await gpu_provider.terminate(pod_id)
        logger.info("activity.terminate_pod.ok pod_id=%s", pod_id)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "does not exist" in msg:
            logger.info("activity.terminate_pod.already_gone pod_id=%s", pod_id)
            return
        # Other errors (auth, network) — re-raise so Temporal retry policy triggers
        logger.warning("activity.terminate_pod.error pod_id=%s error=%s", pod_id, e)
        raise
