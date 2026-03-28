"""DB write helpers for SimulationJob persistence."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from saas.workers.utils import _run_async

logger = logging.getLogger(__name__)


def _extract_key_insight(report: str) -> str | None:
    """Extract the first substantive non-heading line from a markdown report (max 200 chars)."""
    if not report:
        return None
    lines = [line.strip() for line in report.split('\n') if line.strip()]
    # Skip markdown headings, find first content line
    insight_line = next(
        (line for line in lines if not line.startswith('#') and len(line) > 30),
        None
    )
    if insight_line:
        return insight_line[:200]
    return None


def _save_job_results(job_id: int, report: str, chat_log: str, graph_data: str = "{}", key_insight: str | None = None) -> None:
    """Persist pipeline results (report + chat_log + graph_data + key_insight) to the SimulationJob row."""
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
                        "    key_insight = :key_insight, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "report": report,
                        "chat_log": chat_log,
                        "graph_data": graph_data,
                        "key_insight": key_insight,
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
