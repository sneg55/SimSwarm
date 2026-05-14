"""Pipeline-phase activity: submit /job and poll /status until complete."""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from temporalio import activity

from saas.workflows.types import SimParams

logger = logging.getLogger(__name__)


async def _heartbeat_every(interval_s: float) -> None:
    try:
        while True:
            if activity.in_activity():
                activity.heartbeat()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        return


@activity.defn(name="fishcloud.submit_and_poll")
async def submit_and_poll(
    pod_id: str, params: SimParams, markets: list[dict],
) -> dict:
    """POST /job (if pod idle) and poll /status until completion.

    Idempotent: if the pod reports 'running' or 'completed', skip POST and
    go straight to polling. This mirrors the current runner.resume() logic
    and makes the activity safe to retry after a worker restart.
    """
    from saas.jobs.config import JobConfig
    from saas.jobs.pipeline import poll_until_complete
    from saas.jobs.worker_http import submit_job
    from saas.jobs.persistence import (
        _transition_to_running,
        _update_heartbeat_sync,
        _update_pipeline_stage_sync,
    )

    worker_url = f"https://{pod_id}-5000.proxy.runpod.net"

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

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)
        if activity.in_activity():
            activity.heartbeat()

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)
        if activity.in_activity():
            activity.heartbeat()

    async def _status_cb(j_id: int, _status: str) -> None:
        _transition_to_running(j_id)

    heartbeat_task = asyncio.create_task(_heartbeat_every(30))
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Check pod state — if running/completed, skip POST (idempotent reentry)
            try:
                status_resp = await client.get(f"{worker_url}/status", timeout=10)
                status = (
                    status_resp.json().get("status", "unknown")
                    if status_resp.status_code == 200
                    else "unknown"
                )
            except Exception:
                status = "unknown"

            if status in ("running", "completed"):
                logger.info(
                    "activity.submit_and_poll.resume pod_id=%s status=%s",
                    pod_id, status,
                )
            else:
                logger.info("activity.submit_and_poll.submitting pod_id=%s", pod_id)
                await submit_job(worker_url, job_config, client)

            result = await poll_until_complete(
                worker_url, pod_id, job_config, client=client,
                stage_callback=_stage_cb,
                heartbeat_callback=_heartbeat_cb,
                status_callback=_status_cb,
            )
            result["pod_id"] = pod_id
            return result
    finally:
        heartbeat_task.cancel()
