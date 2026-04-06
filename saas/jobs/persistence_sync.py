"""Sync (psycopg2) DB write helpers for SimulationJob — safe to call from Celery tasks."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from saas.jobs.persistence_engine import _get_sync_engine

logger = logging.getLogger(__name__)


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
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping result save for job %d", job_id)
        return

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = create_engine(sync_url)
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
                    "WHERE id = :job_id"
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
        engine.dispose()
    except Exception as exc:
        logger.warning("Could not save results for job %d: %s", job_id, exc)


def _update_pipeline_stage_sync(job_id: int, stage: int) -> None:
    """Update pipeline_stage and set status to RUNNING (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping pipeline_stage update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs SET pipeline_stage = :stage, status = 'RUNNING' "
                    "WHERE id = :job_id AND status != 'COMPLETED'"
                ),
                {"stage": stage, "job_id": job_id},
            )
            conn.commit()
            logger.debug("Set pipeline_stage=%d for job %d", stage, job_id)
    except Exception as exc:
        logger.warning("Could not update pipeline_stage for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_heartbeat_sync(job_id: int) -> None:
    """Update last_heartbeat timestamp (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping heartbeat update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET last_heartbeat = now() WHERE id = :job_id"),
                {"job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not update heartbeat for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_live_status_sync(job_id: int, live_status: dict) -> None:
    """Write live_status JSONB for a running job (sync, for Celery).

    Uses _get_sync_engine() / psycopg2 — never the shared async pool.
    Silently skips if DATABASE_URL is unset (e.g. tests without DB).
    """
    import json
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping live_status update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET live_status = CAST(:live_status AS JSONB) "
                    "WHERE id = :job_id"
                ),
                {"live_status": json.dumps(live_status), "job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not update live_status for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_pod_id(job_id: int, pod_id: str, gpu_provider: str = "runpod") -> None:
    """Persist pod_id to the SimulationJob row immediately after GPU provisioning.

    Uses a sync connection to avoid asyncpg InterfaceError when the async pool
    is busy with concurrent operations (enrichment, heartbeat, etc.).
    """
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping pod_id update for job %d", job_id)
        return

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs SET pod_id = :pod_id, status = 'PROVISIONING', "
                    "gpu_provider = :gpu_provider WHERE id = :job_id"
                ),
                {"pod_id": pod_id, "gpu_provider": gpu_provider, "job_id": job_id},
            )
            conn.commit()
            logger.info("Saved pod_id=%s for job %d (status → PROVISIONING)", pod_id, job_id)
        engine.dispose()
    except Exception as exc:
        logger.warning("Could not save pod_id for job %d: %s", job_id, exc)


def _update_sim_data_available(job_id: int, available: bool) -> None:
    """Mark whether rich simulation data was uploaded to MinIO."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping sim_data_available update for job %d", job_id)
        return

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET sim_data_available = :available WHERE id = :job_id"),
                {"available": available, "job_id": job_id},
            )
            conn.commit()
            logger.info("Set sim_data_available=%s for job %d", available, job_id)
        engine.dispose()
    except Exception as exc:
        logger.warning("Could not update sim_data_available for job %d: %s", job_id, exc)


def _get_job_status(job_id: int) -> str | None:
    """Get current job status (sync, for Celery)."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping status check for job %d", job_id)
        return None

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM simulation_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).first()
            return row[0] if row else None
    finally:
        engine.dispose()


