"""Finalization activities: result upload/handoff, failure marking."""
from __future__ import annotations

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fishcloud.upload_and_finalize")
async def upload_and_finalize(job_id: int, user_id: str, result: dict) -> None:
    """Update job metadata, transition to REPORTING, enqueue report task.

    The result fields (report/chat_log/graph/structured) are persisted
    inside submit_and_poll now; they never traverse Temporal so the
    workflow payload stays small. This activity just handles the
    post-pipeline transitions.

    Raises RuntimeError if sim_data was not uploaded to MinIO — that's
    fatal under the external-report flow.
    """
    from saas.jobs.persistence import (
        _transition_to_reporting,
        _update_job_metadata, _update_sim_data_available,
    )

    pod_id = result.get("pod_id", "")
    provision_seconds = result.get("provision_seconds")
    pipeline_seconds = result.get("pipeline_seconds")

    if pod_id:
        _update_job_metadata(
            job_id=job_id, pod_id=pod_id,
            provision_seconds=provision_seconds,
            pipeline_seconds=pipeline_seconds,
        )

    if not result.get("sim_data_uploaded", False):
        raise RuntimeError(
            "sim_data_upload_failed: artifacts missing from MinIO"
        )

    _update_sim_data_available(job_id, True)
    _transition_to_reporting(job_id)

    import saas.jobs.tasks_report as _tasks_report
    _tasks_report.generate_report_task.apply_async((job_id, user_id))

    logger.info(
        "activity.upload_and_finalize.ok job_id=%d pod_id=%s",
        job_id, pod_id,
    )


@activity.defn(name="fishcloud.mark_failed")
async def mark_failed(job_id: int, error_message: str) -> None:
    """Mark the job FAILED. Idempotent — _mark_job_failed_sync only updates
    rows not already in a terminal state."""
    from saas.jobs.persistence import _mark_job_failed_sync

    _mark_job_failed_sync(job_id, error_message)
    logger.info("activity.mark_failed.ok job_id=%d", job_id)
