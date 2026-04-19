"""Finalization activities: result upload/handoff, credit refund on failure."""
from __future__ import annotations

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fishcloud.upload_and_finalize")
async def upload_and_finalize(job_id: int, user_id: str, result: dict) -> None:
    """Persist sim results, transition to REPORTING, enqueue report task.

    Raises RuntimeError if sim_data was not uploaded to MinIO — that's
    fatal under the external-report flow.
    """
    from saas.jobs.persistence import (
        _save_job_results, _transition_to_reporting,
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

    _save_job_results(
        job_id=job_id,
        report=result.get("report", ""),
        chat_log=result.get("chat_log", ""),
        graph_data=result.get("graph_data", "{}"),
        key_insight=None,
        structured=result.get("structured", "{}"),
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


@activity.defn(name="fishcloud.refund_credits")
async def refund_credits(
    job_id: int, user_id: str, credits: int, error_message: str,
) -> None:
    """Mark the job FAILED and refund credits. Idempotent via the existing
    NOT EXISTS guard in _refund_credits.
    """
    from saas.jobs.persistence import _mark_job_failed_sync
    from saas.jobs.refund import _refund_credits

    _mark_job_failed_sync(job_id, error_message)
    if credits > 0:
        _refund_credits(job_id=job_id, user_id=user_id, credits=credits)
    logger.info(
        "activity.refund_credits.ok job_id=%d credits=%d",
        job_id, credits,
    )
