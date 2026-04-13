"""Re-enqueue logic for jobs orphaned in the REPORTING state."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _recover_reporting_jobs(conn, now):
    """Re-enqueue generate_report_task for jobs stuck in REPORTING.

    A REPORTING job is considered stuck if its last_heartbeat is NULL or
    older than 10 minutes (the report task should complete well within
    the 55-minute retry window; 10 minutes of inactivity implies no Celery
    worker is currently executing the task).
    """
    from sqlalchemy import text
    from saas.jobs.tasks_report import generate_report_task

    stuck = list(conn.execute(
        text(
            "SELECT id, user_id "
            "FROM simulation_jobs "
            "WHERE status = 'REPORTING' "
            "  AND (last_heartbeat IS NULL "
            "       OR last_heartbeat < NOW() - INTERVAL '10 minutes')"
        )
    ))
    requeued = []
    for row in stuck:
        job_id, user_id = row[0], row[1]
        try:
            generate_report_task.apply_async((job_id, user_id))
            logger.warning("recover.reporting_requeued job_id=%d user=%s", job_id, user_id)
            requeued.append({"job_id": job_id, "user_id": user_id})
        except Exception as exc:
            logger.error("recover.reporting_requeue_failed job_id=%d err=%s", job_id, exc)
    return requeued
