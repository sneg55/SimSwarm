"""Orphaned pod cleanup logic."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _get_active_job_pod_ids() -> set[str]:
    """Return RunPod pod IDs for jobs that are currently RUNNING, PENDING, or PROVISIONING.

    Queries the pod_id column directly for an exact match against running pods.
    Returns {"__db_error__"} on failure to prevent accidental termination.
    """
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return {"__db_error__"}

    # Convert async URL to sync for this simple query
    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
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
        return {"__db_error__"}

    return pod_ids


def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job.

    Runs on a 10-minute beat schedule to catch pods orphaned by worker
    restarts, crashes, or failed termination.
    """
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

    # Find pod IDs actively managed by running jobs
    active_pod_ids = _get_active_job_pod_ids()

    terminated = []
    for pod in pods:
        pod_id = pod.get("id", "")
        name = pod.get("name", "")
        # Only clean up pods we created (named fishcloud-sim or simswarm-sim)
        if name not in ("fishcloud-sim", "simswarm-sim"):
            continue
        if pod_id in active_pod_ids:
            continue
        # Pod has no matching active job — terminate it
        try:
            runpod.terminate_pod(pod_id)
            gpu = pod.get("machine", {}).get("gpuDisplayName", "?")
            logger.warning(
                "cleanup.terminated pod_id=%s gpu=%s name=%s", pod_id, gpu, name,
                extra={"event": "cleanup_terminated", "pod_id": pod_id},
            )
            terminated.append(pod_id)
        except Exception as e:
            logger.warning("cleanup.terminate_failed pod_id=%s error=%s", pod_id, e)

    result = {"active_pods": len(pods), "terminated": len(terminated), "pod_ids": terminated}
    if terminated:
        logger.info("cleanup.summary active_pods=%d terminated=%d", len(pods), len(terminated))
    return result
