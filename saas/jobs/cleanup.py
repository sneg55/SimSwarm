"""Orphaned pod cleanup logic."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

from saas.jobs.alerts import send_orphan_alert

logger = logging.getLogger(__name__)

GRACE_PERIOD_SECONDS = 600  # 10 minutes — pods can take 5+ min to provision on spot


def _pod_age_seconds(pod: dict) -> int:
    """Estimate pod age in seconds from lastStatusChange or uptimeInSeconds.

    RunPod's uptimeInSeconds is unreliable (often returns 0).
    Fall back to parsing lastStatusChange timestamp.
    """
    uptime = pod.get("runtime", {}).get("uptimeInSeconds", 0) if pod.get("runtime") else 0
    if uptime and uptime > 0:
        return uptime

    # Parse lastStatusChange: "Rented by User: Sun Mar 29 2026 18:34:45 GMT+0000 ..."
    last_change = pod.get("lastStatusChange", "")
    if last_change:
        # Extract the date part after the colon
        match = re.search(r':\s*(.+?)\s*(?:GMT|$)', last_change)
        if match:
            try:
                dt = datetime.strptime(match.group(1).strip(), "%a %b %d %Y %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                age = int((datetime.now(timezone.utc) - dt).total_seconds())
                return max(0, age)
            except (ValueError, TypeError):
                pass

    return 0


def _get_active_job_pod_ids() -> set[str] | None:
    """Return RunPod pod IDs for active jobs, or None on DB failure."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None

    sync_url = database_url.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT pod_id FROM simulation_jobs "
                    "WHERE status IN ('PENDING', 'RUNNING', 'PROVISIONING') "
                    "AND pod_id IS NOT NULL"
                )
            )
            pod_ids = {row[0] for row in result}
        engine.dispose()
    except Exception as e:
        logger.warning("cleanup.db_error error=%s", e)
        return None

    return pod_ids


def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job."""
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if not runpod_key:
        raise RuntimeError("cleanup: RUNPOD_API_KEY not set — cannot check for orphaned pods")

    try:
        import runpod
        runpod.api_key = runpod_key
    except ImportError:
        raise RuntimeError("cleanup: runpod package not installed")

    pods = runpod.get_pods()
    if not pods:
        return {"active_pods": 0, "terminated": 0}

    active_pod_ids = _get_active_job_pod_ids()

    if active_pod_ids is None:
        logger.warning("cleanup.skipped_db_unreachable")
        send_orphan_alert(
            pod_id="N/A", gpu_type="N/A", uptime_seconds=0,
            reason="cleanup_skipped_db_unreachable",
        )
        return {"skipped": "db_unreachable", "active_pods": len(pods)}

    terminated = []
    for pod in pods:
        pod_id = pod.get("id", "")
        name = pod.get("name", "")
        if name not in ("fishcloud-sim", "simswarm-sim"):
            continue
        if pod_id in active_pod_ids:
            continue

        uptime = _pod_age_seconds(pod)
        if uptime < GRACE_PERIOD_SECONDS:
            logger.info("cleanup.skipped_young pod_id=%s age=%ds", pod_id, uptime)
            continue

        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            logger.warning(
                "cleanup.terminated pod_id=%s gpu=%s uptime=%ds name=%s",
                pod_id, gpu, uptime, name,
                extra={"event": "cleanup_terminated", "pod_id": pod_id},
            )
            terminated.append(pod_id)

            send_orphan_alert(
                pod_id=pod_id, gpu_type=gpu,
                uptime_seconds=uptime, reason="orphan_no_matching_job",
            )
        except Exception as e:
            logger.warning("cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)

    result = {"active_pods": len(pods), "terminated": len(terminated), "pod_ids": terminated}
    if terminated:
        logger.info("cleanup.summary active_pods=%d terminated=%d", len(pods), len(terminated))
    return result
