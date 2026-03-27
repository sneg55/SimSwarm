"""Celery task definitions for FishCloud GPU job orchestration."""
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


def _save_job_results(job_id: int, report: str, chat_log: str) -> None:
    """Persist pipeline results (report + chat_log) to the SimulationJob row."""
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
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "report": report,
                        "chat_log": chat_log,
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
    max_retries=0,
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

        # Persist results to the SimulationJob table
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        _save_job_results(job_id=job_id, report=report, chat_log=chat_log)

        logger.info(
            "Job %d completed — report=%d chars, chat_log=%d chars",
            job_id, len(report), len(chat_log),
        )
        return result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Job %d failed: %s", job_id, error_msg, exc_info=True)

        # Mark DB row as failed
        _mark_job_failed(job_id=job_id, error_message=error_msg)

        # Refund credits
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)

        raise
