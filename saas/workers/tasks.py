"""Celery task definitions for SimSwarm GPU job orchestration."""
from __future__ import annotations

import logging

from saas.workers.celery_app import celery_app
from saas.workers.job_runner import JobConfig, JobRunner
from saas.workers.utils import _run_async, _get_gpu_provider
from saas.workers.persistence import (
    _async_update_heartbeat,
    _async_update_pipeline_stage,
    _async_update_pod_id,
    _extract_key_insight,
    _mark_job_failed,
    _save_job_results,
    _update_enrichment,
    _update_job_metadata,
    _update_job_retry,
)
from saas.workers.refund import _refund_credits
from saas.workers.cleanup import cleanup_orphaned_pods as _cleanup_orphaned_pods_impl
from saas.workers.cleanup import _get_active_job_pod_ids  # noqa: F401 — re-export
from saas.workers.recovery import recover_stale_jobs as _recover_stale_jobs_impl

logger = logging.getLogger(__name__)


@celery_app.task(
    name="fishcloud.run_simulation",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def run_simulation_task(
    self,
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
    model_id: str,
    gpu_type: str,
    max_rounds: int,
    vllm_args: str,
    llm_api_key: str,
    zep_api_key: str,
    credits_charged: int = 0,
    enrich_web: bool = True,
) -> dict:
    """
    Celery task that:
      1. Provisions a GPU instance via RunPod / Vast.ai
      2. Runs the MiroFish 5-step pipeline (run_job.py on the GPU)
      3. Saves report + chat_log to the SimulationJob row
      4. Auto-refunds credits and marks the job failed on any error

    Environment variables consumed:
      RUNPOD_API_KEY   — RunPod API key (primary provider)
      VASTAI_API_KEY   — Vast.ai API key (fallback provider)
      DATABASE_URL     — Async SQLAlchemy URL for result persistence
    """
    # Enrich seed text if enabled
    enriched_seed_text = seed_text
    if enrich_web:
        from saas.workers.enrichment import enrich_seed
        import json as _json
        enrichment = enrich_seed(seed_text, goal)
        if enrichment:
            _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
            enriched_seed_text = seed_text + "\n\n--- Background Research ---\n" + enrichment.summary

    config = JobConfig(
        job_id=job_id,
        user_id=user_id,
        seed_text=enriched_seed_text,  # Use enriched version
        goal=goal,
        tier=tier,
        model_id=model_id,
        gpu_type=gpu_type,
        max_rounds=max_rounds,
        vllm_args=vllm_args,
        llm_api_key=llm_api_key,
        zep_api_key=zep_api_key,
    )

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        await _async_update_pipeline_stage(j_id, stage)

    async def _pod_id_cb(j_id: int, pod_id: str) -> None:
        await _async_update_pod_id(j_id, pod_id)

    async def _heartbeat_cb(j_id: int) -> None:
        await _async_update_heartbeat(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        pod_id_callback=_pod_id_cb,
        heartbeat_callback=_heartbeat_cb,
    )

    try:
        result = _run_async(runner.run(config))

        # Extract metadata from runner result
        pod_id = result.get("pod_id", "")
        provision_seconds = result.get("provision_seconds")
        pipeline_seconds = result.get("pipeline_seconds")

        # Persist metadata (pod_id, timing) to the SimulationJob row
        if pod_id:
            _update_job_metadata(
                job_id=job_id, pod_id=pod_id,
                provision_seconds=provision_seconds,
                pipeline_seconds=pipeline_seconds,
            )

        # Persist results to the SimulationJob table
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        # Extract key insight (first substantive sentence from report, max 200 chars)
        key_insight = _extract_key_insight(report)

        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data, key_insight=key_insight, structured=structured)

        logger.info(
            "job.completed job_id=%d pod_id=%s provision_s=%s pipeline_s=%s",
            job_id, pod_id, provision_seconds, pipeline_seconds,
            extra={"event": "job_completed", "job_id": job_id,
                   "pod_id": pod_id, "duration_s": pipeline_seconds},
        )
        return result

    except Exception as exc:
        from saas.gpu.errors import classify_gpu_error

        error_msg = str(exc)
        error_kind = classify_gpu_error(exc)
        logger.error(
            "job.failed job_id=%d error_kind=%s error=%s",
            job_id, error_kind, error_msg, exc_info=True,
            extra={"event": "job_failed", "job_id": job_id, "error": error_msg},
        )

        if error_kind == "transient" and self.request.retries < self.max_retries:
            _update_job_retry(job_id=job_id, retry_count=self.request.retries + 1)
            raise self.retry(exc=exc)

        # Permanent error or retries exhausted — mark failed and refund
        _mark_job_failed(job_id=job_id, error_message=error_msg)

        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        raise


@celery_app.task(
    name="fishcloud.resume_simulation",
    bind=True,
    max_retries=0,
)
def resume_simulation_task(
    self,
    job_id: int,
    user_id: str,
    pod_id: str,
    credits_charged: int = 0,
) -> dict:
    """Resume polling an existing pod after worker restart.

    Reconnects to a pod that was running a simulation when the worker died.
    Polls /status until complete, saves results, and terminates the pod.
    """
    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        await _async_update_pipeline_stage(j_id, stage)

    async def _heartbeat_cb(j_id: int) -> None:
        await _async_update_heartbeat(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        heartbeat_callback=_heartbeat_cb,
    )

    try:
        result = _run_async(runner.resume(pod_id=pod_id, job_id=job_id))

        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data, structured=structured)

        logger.info(
            "job.resumed_completed job_id=%d pod_id=%s report_chars=%d",
            job_id, pod_id, len(report),
        )
        return result

    except Exception as exc:
        error_msg = f"Resume failed: {exc}"
        logger.error("job.resume_failed job_id=%d pod_id=%s error=%s", job_id, pod_id, error_msg)

        _mark_job_failed(job_id=job_id, error_message=error_msg)
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        # Terminate the pod — it's no use to us anymore
        try:
            _run_async(gpu_provider.terminate(pod_id))
        except Exception:
            pass

        raise


@celery_app.task(name="fishcloud.enrich_retry")
def enrich_retry_task(job_id: int, seed_text: str, goal: str) -> dict:
    """Retry enrichment for a job that failed enrichment initially."""
    from saas.workers.enrichment import enrich_seed
    import json as _json

    enrichment = enrich_seed(seed_text, goal)
    if enrichment:
        _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
        return {"status": "enriched", "summary_length": len(enrichment.summary)}
    return {"status": "failed"}


@celery_app.task(name="fishcloud.cleanup_orphaned_pods")
def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job."""
    return _cleanup_orphaned_pods_impl()


@celery_app.task(name="fishcloud.recover_stale_jobs")
def recover_stale_jobs() -> dict:
    """Find jobs stuck in RUNNING/PROVISIONING after a worker restart and fail+refund them."""
    return _recover_stale_jobs_impl()


@celery_app.task(name="fishcloud.prune_error_events")
def prune_error_events() -> dict:
    """Delete error_events rows older than 30 days."""
    import os
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("prune_error_events: DATABASE_URL not set, skipping")
        return {"deleted": 0}

    sync_url = (
        database_url
        .replace("+asyncpg", "")
        .replace("postgresql://", "postgresql+psycopg2://")
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM error_events WHERE timestamp < :cutoff"),
                {"cutoff": cutoff},
            )
            conn.commit()
            deleted = result.rowcount
        logger.info("prune_error_events: deleted=%d rows older than 30d", deleted)
        return {"deleted": deleted}
    finally:
        engine.dispose()
