"""Recovery logic for stale jobs after worker restarts."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def recover_stale_jobs() -> dict:
    """Find jobs stuck in RUNNING/PROVISIONING after a worker restart and fail+refund them.

    A job is "stale" if:
      - status is PENDING, PROVISIONING, or RUNNING
      - created_at is older than its tier timeout + 10 minutes buffer
      - OR its pod_id no longer exists in RunPod

    Runs on worker startup and every 10 minutes via beat schedule.
    """
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("recovery: DATABASE_URL not set — cannot recover stale jobs")

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")

    # Get active RunPod pods for cross-reference
    active_pods = set()
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if runpod_key:
        try:
            import runpod
            runpod.api_key = runpod_key
            pods = runpod.get_pods() or []
            active_pods = {p.get("id", "") for p in pods}
        except Exception as e:
            logger.warning("recover.runpod_check_failed error=%s", e)

    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            # Find all non-terminal jobs
            result = conn.execute(
                text(
                    "SELECT id, user_id, tier, credits_charged, pod_id, created_at "
                    "FROM simulation_jobs "
                    "WHERE status IN ('PENDING', 'RUNNING', 'PROVISIONING') "
                    "ORDER BY created_at ASC"
                )
            )
            stale_jobs = list(result)

        if not stale_jobs:
            engine.dispose()
            return {"stale_jobs": 0, "recovered": 0}

        # Tier timeout + 10 min buffer
        from saas.workers.job_runner import TIER_TIMEOUTS
        now = datetime.now(timezone.utc)
        recovered = []
        resumed = []

        # Import resume task lazily to avoid circular imports
        from saas.workers.tasks import resume_simulation_task

        with engine.connect() as conn:
            for row in stale_jobs:
                job_id, user_id, tier, credits_charged, pod_id, created_at = row
                timeout = TIER_TIMEOUTS.get(tier, 2700) + 600  # tier timeout + 10 min

                # Make created_at timezone-aware if needed
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                age_seconds = (now - created_at).total_seconds()
                pod_alive = pod_id in active_pods if pod_id else False

                if pod_alive and age_seconds < timeout:
                    # Pod is still running and within timeout — resume polling
                    logger.info(
                        "recover.resuming job_id=%d pod_id=%s age=%ds",
                        job_id, pod_id, int(age_seconds),
                    )
                    resume_simulation_task.delay(
                        job_id=job_id,
                        user_id=user_id,
                        pod_id=pod_id,
                        credits_charged=credits_charged,
                    )
                    resumed.append({"job_id": job_id, "pod_id": pod_id})
                    continue

                # Job is stale — pod gone or past timeout — mark failed and refund
                reason = "pod_gone" if not pod_alive else "timeout"
                error_msg = f"Job recovered after worker restart ({reason}, age={int(age_seconds)}s)"

                conn.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET status = 'FAILED', "
                        "    error_message = :error_message, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id AND status IN ('PENDING', 'RUNNING', 'PROVISIONING')"
                    ),
                    {
                        "error_message": error_msg,
                        "completed_at": now,
                        "job_id": job_id,
                    },
                )

                logger.warning(
                    "recover.failed_job job_id=%d user_id=%s reason=%s age=%ds credits=%d",
                    job_id, user_id, reason, int(age_seconds), credits_charged,
                )
                recovered.append({"job_id": job_id, "reason": reason})

            # Refund credits for recovered jobs
            for item in recovered:
                jid = item["job_id"]
                # Find the job's user and credits from our stale_jobs list
                for row in stale_jobs:
                    if row[0] == jid and row[3] > 0:
                        conn.execute(
                            text(
                                "INSERT INTO credit_entries "
                                "(user_id, amount, description, job_id, created_at) "
                                "VALUES (:user_id, :amount, :description, :job_id, :created_at)"
                            ),
                            {
                                "user_id": row[1],
                                "amount": row[3],
                                "description": f"Refund: job {jid} lost during worker restart",
                                "job_id": jid,
                                "created_at": now,
                            },
                        )
                        logger.info("recover.refunded job_id=%d credits=%d user=%s", jid, row[3], row[1])
                        break

            conn.commit()

        engine.dispose()
        result = {
            "stale_jobs": len(stale_jobs),
            "recovered": len(recovered),
            "resumed": len(resumed),
            "details": recovered,
            "resumed_details": resumed,
        }
        if recovered or resumed:
            logger.warning(
                "recover.summary stale=%d recovered=%d resumed=%d",
                len(stale_jobs), len(recovered), len(resumed),
            )
        return result

    except Exception as e:
        logger.error("recover.error error=%s", e, exc_info=True)
        raise RuntimeError(f"recovery: failed to recover stale jobs: {e}") from e
