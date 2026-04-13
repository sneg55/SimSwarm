"""Staleness detection helpers and pod-status probe for recovery logic."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HEARTBEAT_STALE_POD_DEAD_S = 300    # 5 minutes
HEARTBEAT_STALE_NO_PROGRESS_S = 900  # 15 minutes


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
