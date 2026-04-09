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
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET status = 'COMPLETED', "
                    "    result_report = :report, "
                    "    result_chat_log = :chat_log, "
                    "    result_graph = :graph_data, "
                    "    key_insight = :key_insight, "
                    "    result_structured = :structured, "
                    "    completed_at = :completed_at "
                    "WHERE id = :job_id AND status != 'COMPLETED'"
                ),
                {
                    "report": report,
                    "chat_log": chat_log,
                    "graph_data": graph_data,
                    "key_insight": key_insight,
                    "structured": structured,
                    "completed_at": datetime.now(timezone.utc),
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
