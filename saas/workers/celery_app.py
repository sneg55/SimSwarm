"""Celery application configuration for SimSwarm workers."""
import os

from celery import Celery

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
    beat_schedule={
        "cleanup-orphaned-pods": {
            "task": "fishcloud.cleanup_orphaned_pods",
            "schedule": 600.0,  # every 10 minutes
        },
    },
)
