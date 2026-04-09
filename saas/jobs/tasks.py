"""Celery task definitions for SimSwarm GPU job orchestration."""
from __future__ import annotations

import logging
import os

from saas.workers.celery_app import celery_app
from saas.jobs.runner import JobConfig, JobRunner
from saas.workers.utils import _run_async, _get_gpu_provider
from saas.jobs.persistence import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _update_pod_id,
    _extract_key_insight,
    _mark_job_failed,
    _save_job_results,
    _update_enrichment,
    _update_job_metadata,
    _update_job_retry,
    _update_sim_data_available,
)
from saas.jobs.refund import _refund_credits
from saas.jobs.cleanup import cleanup_orphaned_pods as _cleanup_orphaned_pods_impl
from saas.jobs.cleanup import _get_active_job_pod_ids  # noqa: F401 — re-export
from saas.jobs.recovery import recover_stale_jobs as _recover_stale_jobs_impl
# Import resume + maintenance tasks so Celery autodiscovers them via this module
from saas.jobs.tasks_resume import resume_simulation_task  # noqa: F401 — re-export
from saas.jobs.tasks_maintenance import prune_error_events  # noqa: F401 — re-export

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
    openai_api_key: str = "",
    credits_charged: int = 0,
    enrich_web: bool = True,
    forecast_days: int | None = None,
    target_agents: int = 5,
    upload_urls: dict | None = None,
) -> dict:
    """
    Celery task that:
      1. Provisions a GPU instance via RunPod / Vast.ai
      2. Runs the MiroShark pipeline (run_job.py on the GPU)
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
        from saas.jobs.enrichment import enrich_seed
        from saas.jobs.alerts import send_enrichment_alert
        import json as _json
        enrichment = enrich_seed(seed_text, goal)
        if enrichment:
            _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
            enriched_seed_text = seed_text + "\n\n--- Background Research ---\n" + enrichment.summary
        else:
            logger.warning("job.enrichment_empty job_id=%d", job_id)
            send_enrichment_alert(job_id=job_id, goal=goal)

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
        openai_api_key=openai_api_key,
        # Neo4j credentials read from env — not passed through Celery task args
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        forecast_days=forecast_days,
        target_agents=target_agents,
        upload_urls=upload_urls,
    )

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)

    async def _pod_id_cb(j_id: int, pod_id: str) -> None:
        _update_pod_id(j_id, pod_id)

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)

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

        _save_job_results(
            job_id=job_id, report=report, chat_log=chat_log,
            graph_data=graph_data, key_insight=key_insight, structured=structured,
        )

        # Mark rich simulation data availability
        sim_data_uploaded = result.get("sim_data_uploaded", False)
        if sim_data_uploaded:
            _update_sim_data_available(job_id, True)

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


@celery_app.task(name="fishcloud.enrich_retry")
def enrich_retry_task(job_id: int, seed_text: str, goal: str) -> dict:
    """Retry enrichment for a job that failed enrichment initially."""
    from saas.jobs.enrichment import enrich_seed
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
