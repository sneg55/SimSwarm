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
    _mark_job_failed,
    _save_job_results,
    _update_enrichment,
    _update_markets_config,
    _update_job_metadata,
    _update_job_retry,
    _update_sim_data_available,
    _transition_to_reporting,
    _load_job_snapshot,
    _transition_to_running,
)
from saas.jobs.refund import _refund_credits
from saas.jobs.cleanup import cleanup_orphaned_pods as _cleanup_orphaned_pods_impl
from saas.jobs.cleanup import _get_active_job_pod_ids  # noqa: F401 — re-export
from saas.jobs.recovery import recover_stale_jobs as _recover_stale_jobs_impl
# Import resume + maintenance tasks so Celery autodiscovers them via this module
from saas.jobs.tasks_resume import resume_simulation_task  # noqa: F401 — re-export
from saas.jobs.tasks_maintenance import prune_error_events  # noqa: F401 — re-export
from saas.jobs.tasks_report import generate_report_task  # noqa: F401 — re-export

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
    # Idempotency preamble — a redelivered task (broker timeout, explicit
    # apply_async, worker restart mid-ack) must not re-enrich or provision
    # a second pod. Hand off to the resume path if a live pod already exists.
    snapshot = _load_job_snapshot(job_id)
    if snapshot is not None:
        current_status, existing_pod_id, _retry_count = snapshot
        if current_status in ("COMPLETED", "FAILED", "REFUNDED"):
            logger.info(
                "run.skipping_terminal job_id=%d status=%s",
                job_id, current_status,
            )
            return {"job_id": job_id, "status": "skipped_terminal"}
        # Only hand off when this is a genuine redelivery (retries==0).
        # Celery's own self.retry() path intentionally re-provisions.
        is_redelivery = (
            existing_pod_id
            and current_status in ("PROVISIONING", "RUNNING")
            and self.request.retries == 0
        )
        if is_redelivery:
            from saas.jobs.tasks_resume import resume_simulation_task
            logger.info(
                "run.redelivery_detected job_id=%d pod_id=%s status=%s — "
                "handing to resume",
                job_id, existing_pod_id, current_status,
            )
            resume_simulation_task.delay(
                job_id=job_id, user_id=user_id,
                pod_id=existing_pod_id, credits_charged=credits_charged,
            )
            return {"job_id": job_id, "status": "handed_off", "pod_id": existing_pod_id}

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

    # --- Market derivation -------------------------------------------------
    # Derive 3–5 prediction markets from the (possibly enriched) seed + goal.
    # Fails soft: always returns at least one market.
    from saas.jobs.market_derivation import derive_markets
    derivation = derive_markets(
        goal=goal, enriched_seed=enriched_seed_text, tier=tier,
    )
    markets_config = derivation["markets"]
    logger.info(
        "job.markets_derived job_id=%d source=%s count=%d",
        job_id, derivation["source"], len(markets_config),
    )
    _update_markets_config(job_id, markets_config)

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
        markets_config=markets_config,
    )

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)

    async def _pod_id_cb(j_id: int, pod_id: str) -> None:
        _update_pod_id(j_id, pod_id)

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)

    async def _status_cb(j_id: int, _status: str) -> None:
        _transition_to_running(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        pod_id_callback=_pod_id_cb,
        heartbeat_callback=_heartbeat_cb,
        status_callback=_status_cb,
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

        # Persist non-report results to the SimulationJob table.
        # Report is now produced off-pod; pod returns "" here.
        report = result.get("report", "")  # pod no longer writes this; kept blank
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        _save_job_results(
            job_id=job_id, report=report, chat_log=chat_log,
            graph_data=graph_data, key_insight=None, structured=structured,
        )

        sim_data_uploaded = result.get("sim_data_uploaded", False)

        if not sim_data_uploaded:
            # Upload failure is fatal under the external-report flow — no
            # inline report fallback exists. Fail and refund 100%.
            _mark_job_failed(
                job_id=job_id,
                error_message="sim_data_upload_failed: artifacts missing from MinIO",
            )
            if credits_charged > 0:
                _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)
            logger.warning(
                "job.upload_failed_no_report job_id=%d refunded=%d",
                job_id, credits_charged,
            )
            return result

        # Sim artifacts uploaded — transition to REPORTING and enqueue the
        # external-LLM report task.
        _update_sim_data_available(job_id, True)
        _transition_to_reporting(job_id)

        import saas.jobs.tasks_report as _tasks_report
        _tasks_report.generate_report_task.apply_async((job_id, user_id))

        logger.info(
            "job.sim_complete_report_enqueued job_id=%d pod_id=%s provision_s=%s pipeline_s=%s",
            job_id, pod_id, provision_seconds, pipeline_seconds,
            extra={"event": "job_sim_complete", "job_id": job_id,
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
