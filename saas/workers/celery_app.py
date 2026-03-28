"""Celery application configuration for SimSwarm workers."""
import logging
import os

from celery import Celery
from celery.signals import worker_ready

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
    },
)


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Run stale job recovery when the worker starts up."""
    logger.info("worker.ready — running stale job recovery")
    celery_app.send_task("fishcloud.recover_stale_jobs")
