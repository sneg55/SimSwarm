"""Recovery logic for stale jobs after worker restarts."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from saas.workers.alerts import send_orphan_alert

logger = logging.getLogger(__name__)

HEARTBEAT_STALE_POD_DEAD_S = 300    # 5 minutes


def _check_pod_status(pod_id: str) -> str:
    """Check what the worker pod is doing via its /status endpoint.

    Returns: 'idle', 'running', 'completed', 'failed', or 'unreachable'.
    """
    import httpx

    url = f"https://{pod_id}-5000.proxy.runpod.net/status"
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("status", "unknown")
        return "unreachable"
    except Exception:
        return "unreachable"
HEARTBEAT_STALE_NO_PROGRESS_S = 900  # 15 minutes


def _is_stale(
    last_heartbeat: datetime | None,
    created_at: datetime,
    pod_alive: bool,
    tier_timeout: int,
) -> bool:
    """Determine if a job should be considered stale."""
    now = datetime.now(timezone.utc)

    if last_heartbeat is not None:
        if last_heartbeat.tzinfo is None:
            last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
        hb_age = (now - last_heartbeat).total_seconds()

        if hb_age > HEARTBEAT_STALE_POD_DEAD_S and not pod_alive:
            return True
        if hb_age > HEARTBEAT_STALE_NO_PROGRESS_S:
            return True
        return False

    # No heartbeat — legacy fallback based on created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age = (now - created_at).total_seconds()
    timeout_with_buffer = tier_timeout + 600

    if not pod_alive and age > HEARTBEAT_STALE_POD_DEAD_S:
        return True
    if age > timeout_with_buffer:
        return True
    return False


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
                    "SELECT id, user_id, tier, credits_charged, pod_id, "
                    "created_at, last_heartbeat "
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
        from saas.tiers import TIER_TIMEOUTS
        now = datetime.now(timezone.utc)
        recovered = []
        resumed = []

        # Import resume task lazily to avoid circular imports
        from saas.workers.tasks import resume_simulation_task

        with engine.connect() as conn:
            for row in stale_jobs:
                job_id, user_id, tier, credits_charged, pod_id, created_at, last_heartbeat = row
                timeout = TIER_TIMEOUTS.get(tier, 2700)

                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                pod_alive = pod_id in active_pods if pod_id else False

                if not _is_stale(last_heartbeat, created_at, pod_alive, timeout):
                    # Resume jobs whose pod is alive — check pod status first
                    # to avoid "pod is idle" errors during vLLM warmup
                    if pod_alive and pod_id:
                        pod_status = _check_pod_status(pod_id)
                        if pod_status in ("running", "completed"):
                            logger.info(
                                "recover.resuming job_id=%d pod_id=%s pod_status=%s",
                                job_id, pod_id, pod_status,
                            )
                            resume_simulation_task.delay(
                                job_id=job_id,
                                user_id=user_id,
                                pod_id=pod_id,
                                credits_charged=credits_charged,
                            )
                            resumed.append({"job_id": job_id, "pod_id": pod_id})
                        else:
                            logger.info(
                                "recover.skipping_idle job_id=%d pod_id=%s pod_status=%s",
                                job_id, pod_id, pod_status,
                            )
                    continue

                reason = "heartbeat_stale" if last_heartbeat else "timeout"
                if not pod_alive:
                    reason = "pod_gone"
                age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
                error_msg = (
                    f"Job recovered after worker restart "
                    f"({reason}, age={int(age_seconds)}s)"
                )

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

                # Terminate the orphaned pod
                if pod_id and pod_alive and runpod_key:
                    try:
                        import runpod
                        runpod.api_key = runpod_key
                        runpod.terminate_pod(pod_id)
                        logger.info("recover.terminated_pod job_id=%d pod_id=%s", job_id, pod_id)
                    except Exception as term_exc:
                        logger.warning("recover.terminate_failed job_id=%d pod_id=%s error=%s", job_id, pod_id, term_exc)

                logger.warning(
                    "recover.failed_job job_id=%d user_id=%s reason=%s age=%ds credits=%d",
                    job_id, user_id, reason, int(age_seconds), credits_charged,
                )
                recovered.append({"job_id": job_id, "reason": reason})

                age_s = int(age_seconds)
                send_orphan_alert(
                    pod_id=pod_id or "unknown",
                    gpu_type="unknown",
                    uptime_seconds=age_s,
                    reason=f"recovery_{reason}",
                    job_id=job_id,
                )

            # Refund credits for recovered jobs
            for item in recovered:
                jid = item["job_id"]
                # Find the job's user and credits from our stale_jobs list
                for row in stale_jobs:
                    if row[0] == jid and row[3] > 0:
                        result = conn.execute(
                            text(
                                "INSERT INTO credit_entries "
                                "(user_id, amount, description, job_id, created_at) "
                                "SELECT :user_id, :amount, :description, :job_id, :created_at "
                                "WHERE NOT EXISTS ("
                                "  SELECT 1 FROM credit_entries "
                                "  WHERE job_id = :job_id AND amount > 0"
                                ")"
                            ),
                            {
                                "user_id": row[1],
                                "amount": row[3],
                                "description": f"Refund: job {jid} lost during worker restart",
                                "job_id": jid,
                                "created_at": now,
                            },
                        )
                        if result.rowcount:
                            logger.info("recover.refunded job_id=%d credits=%d user=%s", jid, row[3], row[1])
                        else:
                            logger.info("recover.refund_skipped job_id=%d (already exists)", jid)
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
