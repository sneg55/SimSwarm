"""Sync (psycopg2) job lifecycle write helpers — safe to call from Celery tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from saas.jobs.persistence_engine import _get_sync_engine

logger = logging.getLogger(__name__)


def _mark_job_failed_sync(job_id: int, error_message: str) -> None:
    """Mark a SimulationJob row as failed (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping mark-failed for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET status = 'FAILED', "
                    "    error_message = :error_message, "
                    "    completed_at = :completed_at "
                    "WHERE id = :job_id AND status NOT IN ('COMPLETED', 'REFUNDED')"
                ),
                {
                    "error_message": error_message[:4096],
                    "completed_at": datetime.now(timezone.utc),
                    "job_id": job_id,
                },
            )
            conn.commit()
            if result.rowcount == 0:
                logger.info("Skipped marking job %d as FAILED — already terminal", job_id)
    except Exception as exc:
        logger.warning("Could not mark job %d failed: %s", job_id, exc)
    finally:
        engine.dispose()


def _save_job_results(
    job_id: int,
    report: str,
    chat_log: str,
    graph_data: str = "{}",
    key_insight: str | None = None,
    structured: str | None = None,
) -> None:
    """Persist pipeline results to the SimulationJob row.

    Uses a sync connection to avoid asyncpg InterfaceError — this is the most
    critical save in the pipeline and MUST succeed.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping result save for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            # NB: status/completed_at are NOT set here — under the external-report
            # flow, transitions are owned by _transition_to_reporting + _save_report_result
            # (or _mark_job_failed on the failure path). This helper only writes
            # the non-status result fields captured from the pod.
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET result_report = :report, "
                    "    result_chat_log = :chat_log, "
                    "    result_graph = :graph_data, "
                    "    key_insight = :key_insight, "
                    "    result_structured = :structured "
                    "WHERE id = :job_id AND status NOT IN ('COMPLETED', 'FAILED', 'REFUNDED')"
                ),
                {
                    "report": report,
                    "chat_log": chat_log,
                    "graph_data": graph_data,
                    "key_insight": key_insight,
                    "structured": structured,
                    "job_id": job_id,
                },
            )
            conn.commit()
            logger.info("Saved results for job %d", job_id)
    except Exception as exc:
        logger.warning("Could not save results for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_job_retry_sync(job_id: int, retry_count: int) -> None:
    """Update retry_count and reset status to PROVISIONING (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping retry_count update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET retry_count = :retry_count, "
                    "    status = 'PROVISIONING' "
                    "WHERE id = :job_id"
                ),
                {"retry_count": retry_count, "job_id": job_id},
            )
            conn.commit()
            logger.info("Set retry_count=%d for job %d", retry_count, job_id)
    except Exception as exc:
        logger.warning("Could not update retry_count for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _get_job_config_for_resume(job_id: int):
    """Fetch minimal job config needed to resubmit /job to an idle worker pod.

    Returns a namespace with seed_text, goal, max_rounds, forecast_days,
    target_agents, and upload_urls — or None if not found.
    """
    from sqlalchemy import text
    from types import SimpleNamespace

    engine = _get_sync_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT j.seed_text, j.goal, j.tier, j.enriched_seed, j.forecast_days, "
                    "       m.max_rounds, m.target_agents "
                    "FROM simulation_jobs j "
                    "LEFT JOIN model_routing m ON m.sim_tier = j.tier "
                    "WHERE j.id = :job_id"
                ),
                {"job_id": job_id},
            ).first()
            if not row:
                return None

            seed_text, goal, tier, enriched_seed, forecast_days, max_rounds, target_agents = row
            # Use enriched seed if available (enrichment already ran before provision)
            effective_seed = enriched_seed or seed_text or ""

            from saas.config import Settings
            from saas.storage.minio_client import SimDataStorage
            settings = Settings()
            minio_storage = SimDataStorage(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                bucket=settings.MINIO_BUCKET,
                secure=settings.MINIO_SECURE,
                proxy_base=settings.MINIO_PROXY_BASE,
            )
            upload_urls = minio_storage.generate_upload_urls(job_id=job_id)

            return SimpleNamespace(
                seed_text=effective_seed,
                goal=goal or "",
                max_rounds=max_rounds or 15,
                forecast_days=forecast_days,
                target_agents=target_agents or 5,
                upload_urls=upload_urls,
            )
    except Exception as exc:
        logger.warning("Could not load job config for resume job %d: %s", job_id, exc)
        return None
    finally:
        engine.dispose()


def _get_job_status(job_id: int) -> str | None:
    """Get current job status (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping status check for job %d", job_id)
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM simulation_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).first()
            return row[0] if row else None
    finally:
        engine.dispose()


def _transition_to_reporting(job_id: int) -> None:
    """Move a job from RUNNING → REPORTING.

    Guarded so it's a no-op if the job is already terminal — protects against
    a race where recover_stale_jobs already marked the job failed.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET status = 'REPORTING' "
                    "WHERE id = :job_id AND status IN ('RUNNING', 'PROVISIONING')"
                ),
                {"job_id": job_id},
            )
            conn.commit()
    finally:
        engine.dispose()


def _load_job_artifacts(job_id: int) -> tuple[str, str]:
    """Return (result_chat_log, result_graph) JSON strings for *job_id*.

    Used by the report task to hand already-persisted sim artifacts to
    simswarm.adapter.adapt_structured without re-fetching from MinIO.

    Returns ("[]", "{}") when the engine is not configured (dev/test) or
    when the row is genuinely missing. DB errors propagate so the Celery
    task's existing failure path can mark the job failed and refund.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning(
            "DATABASE_URL not set; returning empty artifacts for job %d", job_id
        )
        return "[]", "{}"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT result_chat_log, result_graph "
                    "FROM simulation_jobs WHERE id = :id"
                ),
                {"id": job_id},
            ).first()
    finally:
        engine.dispose()
    if not row:
        logger.warning("report.artifacts_row_missing job_id=%d", job_id)
        return "[]", "{}"
    return (row[0] or "[]", row[1] or "{}")


def _save_report_result(
    job_id: int,
    report_markdown: str,
    structured: str,
    key_insight: str | None,
) -> None:
    """Persist final report fields and mark COMPLETED."""
    from sqlalchemy import text
    from datetime import datetime, timezone

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET result_report = :report, "
                    "    result_structured = :structured, "
                    "    key_insight = :key_insight, "
                    "    status = 'COMPLETED', "
                    "    completed_at = :completed_at "
                    "WHERE id = :job_id AND status = 'REPORTING'"
                ),
                {
                    "report": report_markdown,
                    "structured": structured,
                    "key_insight": key_insight,
                    "completed_at": datetime.now(timezone.utc),
                    "job_id": job_id,
                },
            )
            conn.commit()
    finally:
        engine.dispose()
