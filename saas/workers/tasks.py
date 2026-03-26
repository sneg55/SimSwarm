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
    import asyncio
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

    try:
        asyncio.get_event_loop().run_until_complete(_do_refund())
    except RuntimeError:
        # No running event loop in this thread
        asyncio.run(_do_refund())


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
    Celery task that provisions a GPU, runs the MiroFish simulation pipeline,
    and auto-refunds credits on failure.
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
    runner = JobRunner(gpu_provider=gpu_provider)

    async def _run():
        return await runner.run(config)

    try:
        try:
            loop = asyncio.get_running_loop()
            # Running loop exists (e.g. tests with asyncio) — use thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _run())
                return future.result()
        except RuntimeError:
            # No running loop — safe to use asyncio.run
            return asyncio.run(_run())
    except Exception as exc:
        logger.error("Job %d failed: %s", job_id, exc, exc_info=True)
        if credits_charged > 0:
            _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)
        raise
