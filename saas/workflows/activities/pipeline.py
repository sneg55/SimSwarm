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
        _save_job_results,
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

    # All three callbacks call sync psycopg2 helpers; without to_thread
    # they block the event loop on every poll iteration, which starves
    # the heartbeat task and every in-loop watchdog/breaker/detector.
    # Sim 151 (2026-05-16) wedged for 30+ min via this path.
    async def _stage_cb(j_id: int, stage: int) -> None:
        await asyncio.to_thread(_update_pipeline_stage_sync, j_id, stage)
        if activity.in_activity():
            activity.heartbeat()

    async def _heartbeat_cb(j_id: int) -> None:
        await asyncio.to_thread(_update_heartbeat_sync, j_id)
        if activity.in_activity():
            activity.heartbeat()

    async def _status_cb(j_id: int, _status: str) -> None:
        await asyncio.to_thread(_transition_to_running, j_id)

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

            # Persist the result fields (report/chat_log/graph/structured)
            # directly to Postgres here, BEFORE returning. Returning these
            # through Temporal exceeded the 4MB gRPC frontend limit on
            # large-tier sims — see sim 142 post-mortem (2026-05-14): a
            # 4.84MB activity completion was rejected by the server, the
            # whole sim was treated as failed and refunded despite running
            # cleanly to round 200/200. Now Temporal only carries small
            # metadata; upload_and_finalize handles the transitions.
            # Sync write — for large sims the chat_log alone can be
            # several MB which makes the INSERT slow; without to_thread
            # the heartbeat task starves while the write is in flight
            # and Temporal kills the activity. Pushing it off the loop
            # keeps heartbeats firing.
            await asyncio.to_thread(
                _save_job_results,
                job_id=params.job_id,
                report=result.get("report", ""),
                chat_log=result.get("chat_log", "[]"),
                graph_data=result.get("graph_data", "{}"),
                key_insight=None,
                structured=result.get("structured", "{}"),
            )

            return {
                "pod_id": pod_id,
                "sim_data_uploaded": result.get("sim_data_uploaded", False),
                "provision_seconds": result.get("provision_seconds"),
                "pipeline_seconds": result.get("pipeline_seconds"),
                "status": "completed",
            }
    finally:
        heartbeat_task.cancel()
