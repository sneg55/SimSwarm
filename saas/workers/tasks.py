"""Celery task definitions for SimSwarm GPU job orchestration."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from saas.workers.celery_app import celery_app
from saas.workers.job_runner import JobConfig, JobRunner

logger = logging.getLogger(__name__)


def _get_gpu_provider():
    """Build a FailoverGPUProvider from environment configuration."""
    from saas.gpu.failover import FailoverGPUProvider

    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    vastai_key = os.getenv("VASTAI_API_KEY", "")

    # Import providers lazily to handle optional runpod package
    try:
        from saas.gpu.runpod_provider import RunPodProvider
        primary = RunPodProvider(api_key=runpod_key)
    except ImportError:
        from saas.gpu.vastai_provider import VastAIProvider
        primary = VastAIProvider(api_key=vastai_key)

    from saas.gpu.vastai_provider import VastAIProvider
    fallback = VastAIProvider(api_key=vastai_key)

    return FailoverGPUProvider(primary=primary, fallback=fallback)


def _refund_credits(job_id: int, user_id: str, credits: int) -> None:
    """Insert a credit refund entry directly into the DB (billing-independent)."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping credit refund for job %d", job_id)
        return

    async def _do_refund():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "INSERT INTO credit_ledger "
                        "(user_id, delta, reason, job_id, created_at) "
                        "VALUES (:user_id, :delta, :reason, :job_id, :created_at)"
                    ),
                    {
                        "user_id": user_id,
                        "delta": credits,
                        "reason": "refund",
                        "job_id": job_id,
                        "created_at": datetime.now(timezone.utc),
                    },
                )
                await session.commit()
                logger.info("Refunded %d credits to user %s for job %d", credits, user_id, job_id)
            except Exception as exc:
                logger.warning("Could not insert credit refund for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_refund())


def _save_job_results(job_id: int, report: str, chat_log: str, graph_data: str = "{}") -> None:
    """Persist pipeline results (report + chat_log + graph_data) to the SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping result save for job %d", job_id)
        return

    async def _do_save():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET status = 'COMPLETED', "
                        "    result_report = :report, "
                        "    result_chat_log = :chat_log, "
                        "    result_graph = :graph_data, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "report": report,
                        "chat_log": chat_log,
                        "graph_data": graph_data,
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id,
                    },
                )
                await session.commit()
                logger.info("Saved results for job %d", job_id)
            except Exception as exc:
                logger.warning("Could not save results for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_save())


def _mark_job_failed(job_id: int, error_message: str) -> None:
    """Mark a SimulationJob row as failed with the given error message."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return

    async def _do_fail():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET status = 'FAILED', "
                        "    error_message = :error_message, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "error_message": error_message[:4096],
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id,
                    },
                )
                await session.commit()
            except Exception as exc:
                logger.warning("Could not mark job %d failed: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_fail())


def _update_pipeline_stage(job_id: int, stage: int) -> None:
    """Update pipeline_stage on a SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return

    async def _do_update():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text("UPDATE simulation_jobs SET pipeline_stage = :stage WHERE id = :job_id"),
                    {"stage": stage, "job_id": job_id},
                )
                await session.commit()
                logger.debug("Set pipeline_stage=%d for job %d", stage, job_id)
            except Exception as exc:
                logger.warning("Could not update pipeline_stage for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_update())


def _update_job_metadata(job_id: int, pod_id: str, provision_seconds: int | None = None, pipeline_seconds: int | None = None) -> None:
    """Persist pod_id and timing metadata to the SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping metadata update for job %d", job_id)
        return

    async def _do_update():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET pod_id = :pod_id, "
                        "    provision_seconds = :provision_seconds, "
                        "    pipeline_seconds = :pipeline_seconds "
                        "WHERE id = :job_id"
                    ),
                    {
                        "pod_id": pod_id,
                        "provision_seconds": provision_seconds,
                        "pipeline_seconds": pipeline_seconds,
                        "job_id": job_id,
                    },
                )
                await session.commit()
                logger.info("Updated metadata for job %d (pod_id=%s)", job_id, pod_id)
            except Exception as exc:
                logger.warning("Could not update metadata for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_update())


def _update_job_retry(job_id: int, retry_count: int) -> None:
    """Update retry_count and reset status to PROVISIONING for a job being retried."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return

    async def _do_update():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET retry_count = :retry_count, "
                        "    status = 'PROVISIONING' "
                        "WHERE id = :job_id"
                    ),
                    {"retry_count": retry_count, "job_id": job_id},
                )
                await session.commit()
                logger.info("Set retry_count=%d for job %d", retry_count, job_id)
            except Exception as exc:
                logger.warning("Could not update retry_count for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_update())


def _run_async(coro) -> object:
    """
    Run an async coroutine from a synchronous Celery worker context.

    Celery workers typically run without a running event loop, so
    ``asyncio.run()`` works.  When called from a thread that already has a
    running loop (e.g. pytest-asyncio tests), we submit the work to a
    dedicated thread pool instead to avoid the "cannot run nested event loop"
    error.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)

    # A running loop exists; schedule the coroutine in a separate thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


@celery_app.task(
    name="fishcloud.run_simulation",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def run_simulation_task(
    self,
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
    model_id: str,
    gpu_type: str,
    max_rounds: int,
    vllm_args: str,
    llm_api_key: str,
    zep_api_key: str,
    credits_charged: int = 0,
) -> dict:
    """
    Celery task that:
      1. Provisions a GPU instance via RunPod / Vast.ai
      2. Runs the MiroFish 5-step pipeline (run_job.py on the GPU)
      3. Saves report + chat_log to the SimulationJob row
      4. Auto-refunds credits and marks the job failed on any error

    Environment variables consumed:
      RUNPOD_API_KEY   — RunPod API key (primary provider)
      VASTAI_API_KEY   — Vast.ai API key (fallback provider)
      DATABASE_URL     — Async SQLAlchemy URL for result persistence
    """
    config = JobConfig(
        job_id=job_id,
        user_id=user_id,
        seed_text=seed_text,
        goal=goal,
        tier=tier,
        model_id=model_id,
        gpu_type=gpu_type,
        max_rounds=max_rounds,
        vllm_args=vllm_args,
        llm_api_key=llm_api_key,
        zep_api_key=zep_api_key,
    )

    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage(j_id, stage)

    runner = JobRunner(gpu_provider=gpu_provider, stage_callback=_stage_cb)

    try:
        result = _run_async(runner.run(config))

        # Extract metadata from runner result
        pod_id = result.get("pod_id", "")
        provision_seconds = result.get("provision_seconds")
        pipeline_seconds = result.get("pipeline_seconds")

        # Persist metadata (pod_id, timing) to the SimulationJob row
        if pod_id:
            _update_job_metadata(
                job_id=job_id, pod_id=pod_id,
                provision_seconds=provision_seconds,
                pipeline_seconds=pipeline_seconds,
            )

        # Persist results to the SimulationJob table
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data)

        logger.info(
            "job.completed job_id=%d pod_id=%s provision_s=%s pipeline_s=%s",
            job_id, pod_id, provision_seconds, pipeline_seconds,
            extra={"event": "job_completed", "job_id": job_id,
                   "pod_id": pod_id, "duration_s": pipeline_seconds},
        )
        return result

    except Exception as exc:
        from saas.gpu.errors import classify_gpu_error

        error_msg = str(exc)
        error_kind = classify_gpu_error(exc)
        logger.error(
            "job.failed job_id=%d error_kind=%s error=%s",
            job_id, error_kind, error_msg, exc_info=True,
            extra={"event": "job_failed", "job_id": job_id, "error": error_msg},
        )

        if error_kind == "transient" and self.request.retries < self.max_retries:
            _update_job_retry(job_id=job_id, retry_count=self.request.retries + 1)
            raise self.retry(exc=exc)

        # Permanent error or retries exhausted — mark failed and refund
        _mark_job_failed(job_id=job_id, error_message=error_msg)

        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        raise


@celery_app.task(
    name="fishcloud.resume_simulation",
    bind=True,
    max_retries=0,
)
def resume_simulation_task(
    self,
    job_id: int,
    user_id: str,
    pod_id: str,
    credits_charged: int = 0,
) -> dict:
    """Resume polling an existing pod after worker restart.

    Reconnects to a pod that was running a simulation when the worker died.
    Polls /status until complete, saves results, and terminates the pod.
    """
    gpu_provider = _get_gpu_provider()

    async def _stage_cb(j_id: int, stage: int) -> None:
        _update_pipeline_stage(j_id, stage)

    runner = JobRunner(gpu_provider=gpu_provider, stage_callback=_stage_cb)

    try:
        result = _run_async(runner.resume(pod_id=pod_id, job_id=job_id))

        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")

        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data)

        logger.info(
            "job.resumed_completed job_id=%d pod_id=%s report_chars=%d",
            job_id, pod_id, len(report),
        )
        return result

    except Exception as exc:
        error_msg = f"Resume failed: {exc}"
        logger.error("job.resume_failed job_id=%d pod_id=%s error=%s", job_id, pod_id, error_msg)

        _mark_job_failed(job_id=job_id, error_message=error_msg)
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        # Terminate the pod — it's no use to us anymore
        try:
            _run_async(gpu_provider.terminate(pod_id))
        except Exception:
            pass

        raise


@celery_app.task(name="fishcloud.cleanup_orphaned_pods")
def cleanup_orphaned_pods() -> dict:
    """Terminate RunPod pods that have no matching RUNNING/PENDING job.

    Runs on a 10-minute beat schedule to catch pods orphaned by worker
    restarts, crashes, or failed termination.
    """
    runpod_key = os.getenv("RUNPOD_API_KEY", "")
    if not runpod_key:
        return {"skipped": "no RUNPOD_API_KEY"}

    try:
        import runpod
        runpod.api_key = runpod_key
    except ImportError:
        return {"skipped": "runpod package not installed"}

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


@celery_app.task(name="fishcloud.recover_stale_jobs")
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
        return {"skipped": "no DATABASE_URL"}

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
        return {"error": str(e)}


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
