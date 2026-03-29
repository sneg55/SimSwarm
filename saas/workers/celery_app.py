"""Celery application configuration for SimSwarm workers."""
import logging
import os

from celery import Celery
from celery.signals import task_failure, worker_ready

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("fishcloud", broker=REDIS_URL, backend=REDIS_URL)

celery_app.autodiscover_tasks(["saas.workers"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Graceful shutdown: wait up to 5 min for running tasks before SIGKILL
    worker_max_tasks_per_child=None,
    beat_schedule={
        "cleanup-orphaned-pods": {
            "task": "fishcloud.cleanup_orphaned_pods",
            "schedule": 600.0,  # every 10 minutes
        },
        "recover-stale-jobs": {
            "task": "fishcloud.recover_stale_jobs",
            "schedule": 600.0,  # every 10 minutes
        },
        "prune-error-events": {
            "task": "fishcloud.prune_error_events",
            "schedule": 86400.0,  # daily
        },
    },
)


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Run stale job recovery when the worker starts up."""
    logger.info("worker.ready — running stale job recovery")
    celery_app.send_task("fishcloud.recover_stale_jobs")


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    """Log Celery task failures to the error_events table."""
    import traceback as tb_module

    try:
        import os
        from datetime import datetime, timezone

        from sqlalchemy import create_engine, text

        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            return

        sync_url = (
            database_url
            .replace("+asyncpg", "")
            .replace("postgresql://", "postgresql+psycopg2://")
        )

        task_name = getattr(sender, "name", str(sender)) if sender else "unknown"
        error_message = str(exception)[:4096] if exception else "unknown error"
        traceback_str = (
            "".join(tb_module.format_tb(traceback))[:8192]
            if traceback is not None
            else ""
        )

        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO error_events "
                        "(timestamp, level, source, message, traceback, job_id) "
                        "VALUES (:ts, :level, :source, :message, :traceback, :job_id)"
                    ),
                    {
                        "ts": datetime.now(timezone.utc),
                        "level": "ERROR",
                        "source": "worker",
                        "message": f"[{task_name}] {error_message}",
                        "traceback": traceback_str,
                        "job_id": None,
                    },
                )
                conn.commit()
        finally:
            engine.dispose()
    except Exception:
        logger.debug("Could not log task failure event", exc_info=True)
