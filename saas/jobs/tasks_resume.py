"""Celery task for resuming simulations after worker restart."""
from __future__ import annotations

import logging

from saas.workers.celery_app import celery_app
from saas.jobs.runner import JobRunner
from saas.workers.utils import _run_async, _get_gpu_provider
from saas.jobs.persistence import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _get_job_status,
    _mark_job_failed,
    _save_job_results,
    _update_sim_data_available,
    _transition_to_reporting,
    _transition_to_running,
    _claim_resume,
    _release_resume,
)
from saas.jobs.refund import _refund_credits

logger = logging.getLogger(__name__)


@celery_app.task(
    name="fishcloud.resume_simulation",
    bind=True,
    max_retries=0,
)
def resume_simulation_task(
    self,
    job_id: int,
    user_id: str,
    pod_id: str,
    credits_charged: int = 0,
) -> dict:
    """Resume polling an existing pod after worker restart.

    Reconnects to a pod that was running a simulation when the worker died.
    Polls /status until complete, saves results, and terminates the pod.
    """
    # Don't overwrite a job that already completed via the original task
    current_status = _get_job_status(job_id)
    if current_status in ('COMPLETED', 'REFUNDED'):
        logger.info("resume.skipping_already_complete job_id=%d status=%s", job_id, current_status)
        return {"job_id": job_id, "status": "already_completed", "skipped": True}

    # Atomic claim — prevents duplicate resume tasks from racing
    task_id = self.request.id or "unknown"
    if not _claim_resume(job_id, task_id):
        logger.info("resume.skipping_already_claimed job_id=%d task_id=%s", job_id, task_id)
        return {"job_id": job_id, "status": "already_claimed", "skipped": True}

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage_sync(j_id, stage)

    async def _heartbeat_cb(j_id: int) -> None:
        _update_heartbeat_sync(j_id)

    async def _status_cb(j_id: int, _status: str) -> None:
        _transition_to_running(j_id)

    runner = JobRunner(
        gpu_provider=gpu_provider,
        stage_callback=_stage_cb,
        heartbeat_callback=_heartbeat_cb,
        status_callback=_status_cb,
    )

    try:
        result = _run_async(runner.resume(pod_id=pod_id, job_id=job_id))

        # Pod no longer returns an inline report; report task fills it later.
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        _save_job_results(
            job_id=job_id, report=report, chat_log=chat_log,
            graph_data=graph_data, key_insight=None, structured=structured,
        )

        sim_data_uploaded = result.get("sim_data_uploaded", False)

        if not sim_data_uploaded:
            # Upload failure is fatal under the external-report flow.
            _mark_job_failed(
                job_id=job_id,
                error_message="sim_data_upload_failed: artifacts missing from MinIO",
            )
            if credits_charged > 0:
                _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)
            logger.warning(
                "job.resume_upload_failed_no_report job_id=%d refunded=%d",
                job_id, credits_charged,
            )
            return result

        _update_sim_data_available(job_id, True)
        _transition_to_reporting(job_id)

        import saas.jobs.tasks_report as _tasks_report
        _tasks_report.generate_report_task.apply_async((job_id, user_id))

        logger.info(
            "job.resumed_sim_complete_report_enqueued job_id=%d pod_id=%s",
            job_id, pod_id,
        )
        return result

    except Exception as exc:
        error_msg = f"Resume failed: {exc}"
        logger.error("job.resume_failed job_id=%d pod_id=%s error=%s", job_id, pod_id, error_msg)

        # Guard against the phantom-resume race: the main run_simulation task
        # may have just completed and moved the job past the states resume
        # owns (PROVISIONING/RUNNING). In that case the pod becoming
        # unreachable is the main task tearing it down after a successful
        # run — not a failure we should clobber with FAILED + a refund.
        current_status = _get_job_status(job_id)
        if current_status in ("PROVISIONING", "RUNNING"):
            _mark_job_failed(job_id=job_id, error_message=error_msg)
            if credits_charged > 0:
                _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)
        else:
            logger.info(
                "job.resume_skip_mark_failed job_id=%d current_status=%s "
                "(main task moved the job past resume's scope)",
                job_id, current_status,
            )

        # Terminate the pod — it's no use to us anymore
        try:
            _run_async(gpu_provider.terminate(pod_id))
        except Exception:
            pass

        raise

    finally:
        _release_resume(job_id)
