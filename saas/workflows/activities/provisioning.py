"""Provisioning-phase activities: pod creation, health wait, teardown."""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from temporalio import activity

from saas.workflows.types import PodInfo, SimParams

logger = logging.getLogger(__name__)


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
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    url = f"https://{existing_pod_id}-5000.proxy.runpod.net/health"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        logger.info(
                            "activity.provision_pod.reuse job_id=%d pod_id=%s",
                            params.job_id, existing_pod_id,
                        )
                        return PodInfo(id=existing_pod_id)
            except Exception as e:
                logger.info(
                    "activity.provision_pod.existing_unhealthy "
                    "job_id=%d pod_id=%s error=%s — creating fresh",
                    params.job_id, existing_pod_id, e,
                )

    _update_pipeline_stage_sync(params.job_id, 0)

    from saas.constants.tiers import TIER_MAX_COST_USD, TIER_TIMEOUTS
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
