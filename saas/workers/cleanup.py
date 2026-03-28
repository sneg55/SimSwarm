"""Orphaned pod cleanup logic."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

GRACE_PERIOD_SECONDS = 180  # 3 minutes


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
        from saas.workers.alerts import send_orphan_alert
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

        uptime = pod.get("runtime", {}).get("uptimeInSeconds", 0)
        if uptime < GRACE_PERIOD_SECONDS:
            logger.info("cleanup.skipped_young pod_id=%s uptime=%ds", pod_id, uptime)
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

            from saas.workers.alerts import send_orphan_alert
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
