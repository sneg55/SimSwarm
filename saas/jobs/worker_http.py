"""Worker pod HTTP helpers: log tail, health polling, job submission.

Split out of `saas.jobs.pipeline` so that module can stay focused on the
poll-until-complete loop. `pipeline` re-exports these for back-compat
with existing call sites and tests.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


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
        "markets_config": config.markets_config,
        "timeout_seconds": config.timeout_seconds,
    }, timeout=30)
    if resp.status_code != 200:
        try:
            error_body = resp.json()
            error_msg = error_body.get("error", resp.text[:2000])
        except Exception:
            error_msg = resp.text[:2000]
        # 409 Conflict semantically means "already running" regardless of
        # body — and even with a non-409 status, if the body is empty
        # treat it as "already running" rather than fail the whole sim
        # over an unparseable error. Sim 154 (2026-05-18) failed because
        # the old string-match check ("already running" in error_msg)
        # didn't fire on an empty error_msg.
        if (resp.status_code == 409
                or not error_msg.strip()
                or "already running" in error_msg.lower()):
            logger.info(
                "Worker rejected job_post (status=%s, msg=%r) — assuming "
                "job already running, falling through to /status poll",
                resp.status_code, error_msg[:200],
            )
            return
        raise RuntimeError(f"Worker rejected job: {error_msg}")
    logger.info("Job accepted by worker, polling /status...")
