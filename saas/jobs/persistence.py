"""DB write helpers for SimulationJob persistence.

This module is a re-export shim. Implementation lives in:
  - persistence_engine.py  — engine/session factory helpers
  - persistence_sync.py    — sync (psycopg2) helpers for Celery tasks
  - persistence_async.py   — async helpers for async contexts

_claim_resume and _release_resume are defined here so that
patch("saas.jobs.persistence._get_sync_engine") correctly intercepts them
in tests.
"""
from __future__ import annotations

import logging

# Engine helpers (imported first — used by functions defined below)
from saas.jobs.persistence_engine import (
    _get_sync_engine,
    _get_worker_session_factory,
)

# Sync helpers (psycopg2 / Celery-safe) — split across two files by concern
from saas.jobs.persistence_sync import (
    _mark_job_failed_sync,
    _save_job_results,
    _update_job_retry_sync,
    _get_job_status,
    _get_job_config_for_resume,
)
from saas.jobs.persistence_sync_progress import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _update_live_status_sync,
    _update_pod_id,
    _update_sim_data_available,
    _update_enrichment_sync,
)

# Async helpers
from saas.jobs.persistence_async import (
    _update_pipeline_stage,
    _async_update_pipeline_stage,
    _async_update_pod_id,
    _update_job_metadata,
    _update_heartbeat,
    _async_update_heartbeat,
)

# Aliases: tasks.py imports these names — route to the sync versions
_update_enrichment = _update_enrichment_sync
_mark_job_failed = _mark_job_failed_sync
_update_job_retry = _update_job_retry_sync

logger = logging.getLogger(__name__)


def _extract_key_insight(report: str) -> str | None:
    """Extract the first substantive non-heading line from a markdown report (max 200 chars)."""
    if not report:
        return None
    lines = [line.strip() for line in report.split('\n') if line.strip()]
    insight_line = next(
        (line for line in lines if not line.startswith('#') and len(line) > 30),
        None
    )
    if insight_line:
        return insight_line[:200]
    return None


def _claim_resume(job_id: int, task_id: str) -> bool:
    """Atomically claim a job for resume. Returns True if claimed, False if already taken."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET resume_task_id = :task_id "
                    "WHERE id = :job_id "
                    "  AND status NOT IN ('COMPLETED', 'FAILED', 'REFUNDED') "
                    "  AND resume_task_id IS NULL "
                    "RETURNING id"
                ),
                {"task_id": task_id, "job_id": job_id},
            ).first()
            conn.commit()
            if row:
                logger.info("resume.claimed job_id=%d task_id=%s", job_id, task_id)
                return True
            logger.info("resume.claim_rejected job_id=%d task_id=%s", job_id, task_id)
            return False
    except Exception as exc:
        logger.warning("resume.claim_error job_id=%d: %s", job_id, exc)
        return False
    finally:
        engine.dispose()


def _release_resume(job_id: int) -> None:
    """Clear resume_task_id after resume completes (success or failure)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET resume_task_id = NULL WHERE id = :job_id"),
                {"job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("resume.release_error job_id=%d: %s", job_id, exc)
    finally:
        engine.dispose()


__all__ = [
    "_extract_key_insight",
    "_get_sync_engine",
    "_get_worker_session_factory",
    "_mark_job_failed_sync",
    "_save_job_results",
    "_update_job_retry_sync",
    "_update_pipeline_stage_sync",
    "_update_heartbeat_sync",
    "_update_live_status_sync",
    "_update_pod_id",
    "_update_sim_data_available",
    "_update_enrichment_sync",
    "_get_job_status",
    "_get_job_config_for_resume",
    "_claim_resume",
    "_release_resume",
    "_mark_job_failed",
    "_update_pipeline_stage",
    "_async_update_pipeline_stage",
    "_async_update_pod_id",
    "_update_job_metadata",
    "_update_heartbeat",
    "_async_update_heartbeat",
    "_update_enrichment",
    "_update_job_retry",
]
