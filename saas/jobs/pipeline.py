"""Pipeline status polling. Worker HTTP helpers live in `worker_http`."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time

import httpx

from saas.jobs.persistence import _update_live_status_sync
from saas.jobs.status import _infer_pipeline_stage, _extract_live_status

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_S = 60  # how often to update last_heartbeat during polling


async def poll_until_complete(
    worker_url: str, instance_id: str, config,
    client: httpx.AsyncClient | None = None,
    stage_callback=None, heartbeat_callback=None,
    status_callback=None,
) -> dict:
    """Poll /status until completed or failed (up to tier timeout).

    Shared by execute_pipeline (normal flow) and resume (reconnect flow).
    When *client* is provided the caller owns the lifecycle; otherwise a
    temporary client is created for backward-compat (resume path).
    """

    @contextlib.asynccontextmanager
    async def _ensure_client():
        if client is not None:
            yield client
        else:
            async with httpx.AsyncClient(timeout=15) as _c:
                yield _c

    from saas.constants.tiers import TIER_STUCK_THRESHOLD_S

    MAX_CONSECUTIVE_FAILURES = 5

    async with _ensure_client() as http:
        poll_start = time.monotonic()
        poll_interval = 10
        max_polls = max(360, config.timeout_seconds // poll_interval)
        stuck_threshold_s = TIER_STUCK_THRESHOLD_S.get(
            getattr(config, "tier", None), 600,
        )
        last_stage: int | None = None
        last_heartbeat_time = 0.0
        _last_round: int | None = None
        _last_round_progress_at = poll_start
        _last_log_lines: list[str] = []
        _last_chat_count: int = 0
        _running_fired = False
        consecutive_failures = 0
        for poll in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                status_resp = await http.get(f"{worker_url}/status")
                status_data = status_resp.json()
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Status poll {poll + 1} failed: {e}")
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(
                        f"Pod unreachable: {MAX_CONSECUTIVE_FAILURES} consecutive poll failures"
                    )
                continue

            # Update heartbeat periodically
            now_mono = time.monotonic()
            if (now_mono - last_heartbeat_time >= HEARTBEAT_INTERVAL_S
                    and heartbeat_callback is not None):
                last_heartbeat_time = now_mono
                try:
                    await heartbeat_callback(config.job_id)
                except Exception:
                    pass

            # Round-progress watchdog. Only meaningful once the worker has
            # reported at least one round — before that we're still in
            # provisioning/vLLM warmup and stuckness is expected.
            if _last_round is not None and _last_round > 0:
                stalled_s = now_mono - _last_round_progress_at
                if stalled_s > stuck_threshold_s:
                    raise RuntimeError(
                        f"Sim stuck: no round progress for {int(stalled_s)}s "
                        f"at round {_last_round} (tier={getattr(config, 'tier', '?')}, "
                        f"threshold={stuck_threshold_s}s)"
                    )

            job_status = status_data.get("status", "unknown")

            # First time the worker reports it's running, flip PROVISIONING→RUNNING.
            if (not _running_fired and job_status == "running"
                    and status_callback is not None):
                _running_fired = True
                try:
                    await status_callback(config.job_id, "RUNNING")
                except Exception as cb_exc:
                    logger.warning(f"Status callback failed: {cb_exc}")

            if poll % 2 == 0:  # Poll logs every ~20s
                elapsed = int(time.monotonic() - poll_start)
                logger.info(
                    f"Pipeline status: {job_status} "
                    f"({elapsed}s elapsed, poll {poll + 1}/{max_polls})")
                # Pull recent pipeline logs
                log_lines = []
                try:
                    log_resp = await http.get(
                        f"{worker_url}/logs?tail=20&source=pipeline", timeout=10)
                    if log_resp.status_code == 200:
                        log_data = log_resp.json()
                        log_lines = log_data.get("lines", [])
                        for line in log_lines[-5:]:
                            logger.info(f"  [worker] {line}")
                except Exception:
                    pass

                # Infer pipeline stage from logs and notify callback if changed
                stage = _infer_pipeline_stage(log_lines)
                if stage is not None and stage != last_stage:
                    last_stage = stage
                    logger.info(f"Pipeline stage updated to {stage}")
                    if stage_callback is not None:
                        try:
                            await stage_callback(config.job_id, stage)
                        except Exception as cb_exc:
                            logger.warning(f"Stage callback failed: {cb_exc}")

                # Build live_status from log data
                max_rounds = getattr(config, "max_rounds", None)
                live = _extract_live_status(log_lines, max_rounds=max_rounds)

                # Fetch partial chat when simulation stage is active
                if (last_stage or 0) >= 3:
                    try:
                        chat_resp = await http.get(
                            f"{worker_url}/partial_chat?tail=10", timeout=10)
                        if chat_resp.status_code == 200:
                            live["partial_chat"] = chat_resp.json().get("messages", [])
                    except Exception:
                        live["partial_chat"] = []

                live["updated_at"] = time.time()

                # Write to DB only when something has changed
                new_round = live.get("round")
                new_log_lines = live.get("log_lines", [])
                new_chat_count = len(live.get("partial_chat", []))
                if (
                    new_round != _last_round
                    or new_log_lines != _last_log_lines
                    or new_chat_count != _last_chat_count
                ):
                    _last_round = new_round
                    _last_log_lines = new_log_lines
                    _last_chat_count = new_chat_count
                    try:
                        _update_live_status_sync(config.job_id, live)
                    except Exception as exc:
                        logger.warning(
                            "live_status write failed for job %d: %s", config.job_id, exc)

            if job_status == "completed":
                result = status_data
                elapsed = int(time.monotonic() - poll_start)
                logger.info(
                    f"Pipeline completed in {elapsed}s!",
                    extra={"event": "pipeline_completed", "job_id": config.job_id,
                           "elapsed_s": elapsed},
                )
                break
            elif job_status == "failed":
                raw_error = status_data.get("error", "Unknown error")
                stdout = status_data.get("stdout", "")
                logger.error(f"Pipeline failed: {raw_error}")
                if stdout:
                    logger.error(f"Pipeline stdout: {stdout[:2000]}")
                # Extract first meaningful line — full log stays in Celery logs
                first_line = raw_error.split("\n")[0][:200]
                raise RuntimeError(f"Worker pipeline failed: {first_line}")
        else:
            raise TimeoutError(
                f"Pipeline did not complete within {max_polls * poll_interval}s")

    return {
        "job_id": config.job_id,
        "instance_id": instance_id,
        "report": result.get("report", ""),
        "chat_log": result.get("chat_log", "[]"),
        "graph_data": result.get("graph_data", "{}"),
        "structured": result.get("structured", "{}"),
        "sim_data_uploaded": result.get("sim_data_uploaded", False),
        "status": "completed",
    }
