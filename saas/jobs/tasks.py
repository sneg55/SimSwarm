"""Celery task definitions for SimSwarm maintenance jobs."""
from __future__ import annotations

import logging

from saas.workers.celery_app import celery_app
from saas.jobs.persistence import (
    _update_enrichment,
)
from saas.jobs.cleanup import cleanup_orphaned_pods as _cleanup_orphaned_pods_impl
from saas.jobs.cleanup import _get_active_job_pod_ids  # noqa: F401 — re-export
# Import maintenance + report tasks so Celery autodiscovers them via this module
from saas.jobs.tasks_maintenance import prune_error_events  # noqa: F401 — re-export
from saas.jobs.tasks_report import generate_report_task  # noqa: F401 — re-export

logger = logging.getLogger(__name__)


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
