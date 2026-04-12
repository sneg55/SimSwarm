"""Pipeline execution: health polling, job submission, status polling."""
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


async def log_worker_output(
    worker_url: str, source: str = "all", tail: int = 20,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Pull recent logs from the worker pod and emit them."""
    try:
        if client is not None:
            resp = await client.get(f"{worker_url}/logs?tail={tail}&source={source}")
        else:
            async with httpx.AsyncClient(timeout=10) as _client:
                resp = await _client.get(f"{worker_url}/logs?tail={tail}&source={source}")
        if resp.status_code == 200:
            data = resp.json()
            for line in data.get("lines", []):
                logger.info(f"  [{source}] {line}")
    except Exception:
        pass


async def wait_for_worker_health(
    worker_url: str, client: httpx.AsyncClient,
) -> None:
    """Poll /health until the worker API (and vLLM) is ready.

    Raises TimeoutError after 15 minutes (180 attempts * 5s).
    """
    health_start = time.monotonic()
    logger.info(f"Waiting for worker API at {worker_url}/health ...")
    for attempt in range(180):  # 15 min max (180 * 5s)
        try:
            resp = await client.get(f"{worker_url}/health", timeout=10)
            if resp.status_code == 200:
                elapsed = int(time.monotonic() - health_start)
                health_data = resp.json() if resp.headers.get(
                    "content-type", "").startswith("application/json") else {}
                vllm_ready = health_data.get("vllm_ready", "?")
                logger.info(
                    f"Worker API ready in {elapsed}s (vllm_ready={vllm_ready})",
                    extra={"event": "health_ready", "elapsed_s": elapsed},
                )
                return
            elif attempt % 6 == 0:  # every 30s
                elapsed = int(time.monotonic() - health_start)
                try:
                    health_data = resp.json()
                    logger.info(f"Worker health: {health_data} ({elapsed}s elapsed)")
                except Exception:
                    logger.info(f"Worker health: HTTP {resp.status_code} ({elapsed}s elapsed)")
                # Pull vLLM logs while waiting -- key debugging info
                await log_worker_output(worker_url, source="vllm", tail=20, client=client)
        except httpx.ConnectError:
            if attempt % 12 == 0:  # every 60s
                elapsed = int(time.monotonic() - health_start)
                logger.info(
                    f"Worker not reachable yet ({elapsed}s elapsed, attempt {attempt + 1}/180)")
        except Exception as e:
            if attempt % 12 == 0:
                elapsed = int(time.monotonic() - health_start)
                logger.info(f"Worker health check: {type(e).__name__} ({elapsed}s elapsed)")
        await asyncio.sleep(5)

    # Exhausted all attempts
    elapsed = int(time.monotonic() - health_start)
    logger.error(f"Worker health timeout after {elapsed}s -- dumping vLLM and pipeline logs:")
    await log_worker_output(worker_url, source="vllm", tail=50, client=client)
    await log_worker_output(worker_url, source="pipeline", tail=20, client=client)
    raise TimeoutError(f"Worker API at {worker_url} did not become ready after {elapsed}s")


async def submit_job(worker_url: str, config, client: httpx.AsyncClient) -> None:
    """POST /job to the worker. Raises RuntimeError on rejection — except when
    the worker says a job is already running, which means the recover task
    claimed the pod during our wait_for_worker_health. In that case the work
    is already happening on the same pod; we just hand off to poll_until_complete."""
    logger.info(f"Submitting job to {worker_url}/job (max_rounds={config.max_rounds})")
    resp = await client.post(f"{worker_url}/job", json={
        "seed_text": config.seed_text,
        "goal": config.goal,
        "max_rounds": config.max_rounds,
        "forecast_days": config.forecast_days,
        "target_agents": config.target_agents,
        "upload_urls": config.upload_urls,
    }, timeout=30)
    if resp.status_code != 200:
        try:
            error_body = resp.json()
            error_msg = error_body.get("error", resp.text[:2000])
        except Exception:
            error_msg = resp.text[:2000]
        if "already running" in error_msg.lower():
            logger.info(
                "Worker reports a job is already running on this pod "
                "(recover task got there first) — falling through to /status poll"
            )
            return
        raise RuntimeError(f"Worker rejected job: {error_msg}")
    logger.info("Job accepted by worker, polling /status...")


async def poll_until_complete(
    worker_url: str, instance_id: str, config,
    client: httpx.AsyncClient | None = None,
    stage_callback=None, heartbeat_callback=None,
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

    MAX_CONSECUTIVE_FAILURES = 5

    async with _ensure_client() as http:
        poll_start = time.monotonic()
        poll_interval = 10
        max_polls = max(360, config.timeout_seconds // poll_interval)
        last_stage: int | None = None
        last_heartbeat_time = 0.0
        _last_round: int | None = None
        _last_log_lines: list[str] = []
        _last_chat_count: int = 0
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

            job_status = status_data.get("status", "unknown")

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
