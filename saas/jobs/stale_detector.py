"""Stale-job detector — backstop for jobs that Temporal has lost or that
are stuck past their tier budget.

A "stale" job is one whose DB status is still live (PENDING, PROVISIONING,
RUNNING, REPORTING) but either:
  a) its Temporal workflow is gone (not found / failed / timed_out / canceled
     / terminated without completing), or
  b) it has been in that live status longer than the expected budget for
     that phase with room to spare.

For each stale job we mark it FAILED, refund the user, and (best-effort)
terminate any lingering pod. This closes the gap left by F1 (upload stall),
F2 (celery report worker down), and T1 (temporal data loss).

Runs every 15 min via Celery beat.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from saas.constants.tiers import TIER_TIMEOUTS

logger = logging.getLogger(__name__)

# Phase budgets (seconds): max wall-clock we'll allow a job to sit in each
# live status before declaring it stale. Deliberately generous — the goal is
# backstop, not aggressive reaping.
_PENDING_BUDGET_S = 300               # 5 min — API→workflow start should be seconds
_PROVISIONING_BUDGET_S = 60 * 60      # 1 h — bad-host retry + wait_for_health ≤~45 min
_REPORTING_BUDGET_S = 60 * 60 + 900   # 75 min — report task retry window ≈55 min + slack


def _sync_db_url() -> str | None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None
    return database_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )


def _running_budget_s(tier: str | None) -> int:
    """Allow the full tier timeout + 10 min grace for RUNNING jobs."""
    return TIER_TIMEOUTS.get(tier or "large", 43200) + 600


def _phase_budget_s(status: str, tier: str | None) -> int:
    if status == "PENDING":
        return _PENDING_BUDGET_S
    if status == "PROVISIONING":
        return _PROVISIONING_BUDGET_S
    if status == "RUNNING":
        return _running_budget_s(tier)
    if status == "REPORTING":
        return _REPORTING_BUDGET_S
    return 24 * 60 * 60  # unknown live status — 24h fallback


def _load_live_jobs() -> list[dict]:
    sync_url = _sync_db_url()
    if sync_url is None:
        return []
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, user_id, status, tier, credits_charged, pod_id, "
                    "workflow_id, created_at "
                    "FROM simulation_jobs "
                    "WHERE status IN ('PENDING', 'PROVISIONING', 'RUNNING', 'REPORTING')"
                )
            ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        engine.dispose()


async def _workflow_is_terminal(workflow_id: str) -> bool:
    """True if the Temporal workflow for this job_id is gone or finished.

    Returns False only when the workflow is actively RUNNING or we can't
    reach Temporal (fail-safe: don't mark stale if we can't verify).
    """
    from temporalio.client import WorkflowExecutionStatus
    from temporalio.service import RPCError

    from saas.workflows.client import get_temporal_client

    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
    except RPCError as e:
        msg = str(e).lower()
        if "not found" in msg or "does not exist" in msg:
            return True
        logger.warning("stale.temporal_rpc_error workflow_id=%s error=%s", workflow_id, e)
        return False
    except Exception as e:
        logger.warning("stale.temporal_error workflow_id=%s error=%s", workflow_id, e)
        return False
    return desc.status != WorkflowExecutionStatus.RUNNING


def _best_effort_terminate_pod(pod_id: str) -> None:
    """Best-effort pod kill — logs but swallows all errors."""
    if not pod_id:
        return
    try:
        import runpod
        runpod.api_key = os.getenv("RUNPOD_API_KEY", "")
        runpod.terminate_pod(pod_id)
        logger.info("stale.pod_terminated pod_id=%s", pod_id)
    except Exception as e:
        logger.warning("stale.pod_terminate_failed pod_id=%s error=%s", pod_id, e)


def _reconcile_stale_job(job: dict, reason: str) -> None:
    """Mark the job FAILED, refund the user, and terminate its pod."""
    from saas.jobs.persistence import _mark_job_failed_sync
    from saas.jobs.refund import _refund_credits

    job_id = job["id"]
    user_id = job["user_id"]
    credits = int(job.get("credits_charged") or 0)

    _mark_job_failed_sync(job_id, f"stale_detector: {reason}")
    if credits > 0:
        _refund_credits(job_id=job_id, user_id=user_id, credits=credits)
    _best_effort_terminate_pod(job.get("pod_id") or "")
    logger.warning(
        "stale.reconciled job_id=%d status_was=%s reason=%s refunded=%d",
        job_id, job["status"], reason, credits,
    )


def detect_stale_jobs() -> dict:
    """Scan for stale jobs and reconcile them.

    Returns a summary dict for Celery task inspection.
    """
    jobs = _load_live_jobs()
    if not jobs:
        return {"scanned": 0, "reconciled": 0}

    now = datetime.now(timezone.utc)
    reconciled: list[int] = []

    for job in jobs:
        created_at = job["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_s = (now - created_at).total_seconds()

        budget = _phase_budget_s(job["status"], job.get("tier"))
        workflow_id = job.get("workflow_id")

        if age_s < budget:
            continue  # still within phase budget

        # Over budget. Check Temporal before acting — if the workflow is
        # actively RUNNING, Temporal is still trying, don't step on it.
        reason = f"over_budget age={int(age_s)}s budget={budget}s status={job['status']}"
        if workflow_id:
            try:
                terminal = asyncio.run(_workflow_is_terminal(workflow_id))
            except Exception as e:
                logger.warning(
                    "stale.workflow_check_failed job_id=%d workflow_id=%s error=%s",
                    job["id"], workflow_id, e,
                )
                continue
            if not terminal:
                logger.info(
                    "stale.over_budget_but_temporal_running job_id=%d age=%ds",
                    job["id"], int(age_s),
                )
                continue
            reason += " workflow=terminal"
        else:
            reason += " workflow=missing"

        _reconcile_stale_job(job, reason)
        reconciled.append(job["id"])

    if reconciled:
        logger.warning(
            "stale.summary scanned=%d reconciled=%d ids=%s",
            len(jobs), len(reconciled), reconciled,
        )
    return {
        "scanned": len(jobs),
        "reconciled": len(reconciled),
        "job_ids": reconciled,
    }
