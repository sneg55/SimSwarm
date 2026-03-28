"""Fire-and-forget webhook alerts for GPU orphan events."""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GPU_HOURLY_RATES: dict[str, float] = {
    "A100 PCIe": 1.64,
    "A100": 1.64,
    "L40S": 1.24,
    "RTX 4090": 0.69,
    "RTX A6000": 0.79,
    "H100": 3.89,
    "A40": 0.79,
}


def send_orphan_alert(
    pod_id: str,
    gpu_type: str,
    uptime_seconds: int,
    reason: str,
    job_id: int | None = None,
) -> None:
    """POST an alert to the configured webhook URL. Never raises."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
    if not webhook_url:
        return

    hours = uptime_seconds / 3600
    rate = GPU_HOURLY_RATES.get(gpu_type, 1.00)
    estimated_cost = round(hours * rate, 2)

    text = (
        f":warning: *GPU Orphan Terminated*\n"
        f"• Pod: `{pod_id}`\n"
        f"• GPU: {gpu_type}\n"
        f"• Uptime: {int(hours)}h {int((hours % 1) * 60)}m\n"
        f"• Est. wasted cost: ${estimated_cost}\n"
        f"• Reason: {reason}"
    )
    if job_id is not None:
        text += f"\n• Job ID: {job_id}"

    try:
        httpx.post(
            webhook_url,
            json={"text": text},
            timeout=10,
        )
    except Exception as e:
        logger.warning("alert.send_failed error=%s", e)
