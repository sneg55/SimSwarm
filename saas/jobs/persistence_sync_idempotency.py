"""Sync helpers that guard Celery task redelivery.

`_load_job_snapshot` feeds the idempotency preamble in
`run_simulation_task` so a re-delivered task can detect an already-running
job and hand off to the resume path instead of provisioning a second pod.

`_transition_to_running` flips PROVISIONING → RUNNING once the worker
reports pipeline activity, so `recover_stale_jobs` and `cleanup_orphaned_pods`
see the job in its true state.
"""
from __future__ import annotations

import logging

from saas.jobs.persistence_engine import _get_sync_engine

logger = logging.getLogger(__name__)


def _load_job_snapshot(job_id: int):
    """Return (status, pod_id, retry_count) or None.

    None signals "can't tell" — caller proceeds with the fresh-run path.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT status, pod_id, retry_count "
                    "FROM simulation_jobs WHERE id = :job_id"
                ),
                {"job_id": job_id},
            ).first()
            if not row:
                return None
            return (row[0], row[1], row[2])
    except Exception as exc:
        logger.warning("Could not load job snapshot for job %d: %s", job_id, exc)
        return None
    finally:
        engine.dispose()


def _transition_to_running(job_id: int) -> None:
    """Idempotent PROVISIONING → RUNNING.

    Guarded by `WHERE status='PROVISIONING'` so concurrent callers (main
    task + resume task) can succeed at most once, and a job already past
    PROVISIONING cannot be dragged back.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET status = 'RUNNING' "
                    "WHERE id = :job_id AND status = 'PROVISIONING'"
                ),
                {"job_id": job_id},
            )
            conn.commit()
            if result.rowcount:
                logger.info("job.transition_running job_id=%d", job_id)
    except Exception as exc:
        logger.warning("Could not transition job %d to RUNNING: %s", job_id, exc)
    finally:
        engine.dispose()
