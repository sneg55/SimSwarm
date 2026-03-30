"""DB write helpers for SimulationJob persistence."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from saas.workers.utils import _run_async

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level lazy DB engine — avoids creating a new engine per helper call
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None


def _get_worker_session_factory():
    """Return a shared async_sessionmaker, creating the engine on first call."""
    global _engine, _session_factory
    if _session_factory is None:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            return None
        _engine = create_async_engine(database_url, pool_size=2, max_overflow=3)
        _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


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


def _save_job_results(job_id: int, report: str, chat_log: str, graph_data: str = "{}", key_insight: str | None = None, structured: str | None = None) -> None:
    """Persist pipeline results (report + chat_log + graph_data + key_insight + structured) to the SimulationJob row."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        logger.warning("DATABASE_URL not set; skipping result save for job %d", job_id)
        return

    async def _do_save():
        async with factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET status = 'COMPLETED', "
                        "    result_report = :report, "
                        "    result_chat_log = :chat_log, "
                        "    result_graph = :graph_data, "
                        "    key_insight = :key_insight, "
                        "    result_structured = :structured, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "report": report,
                        "chat_log": chat_log,
                        "graph_data": graph_data,
                        "key_insight": key_insight,
                        "structured": structured,
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id,
                    },
                )
                await session.commit()
                logger.info("Saved results for job %d", job_id)
            except Exception as exc:
                logger.warning("Could not save results for job %d: %s", job_id, exc)

    _run_async(_do_save())


def _mark_job_failed(job_id: int, error_message: str) -> None:
    """Mark a SimulationJob row as failed with the given error message."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return

    async def _do_fail():
        async with factory() as session:
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

    _run_async(_do_fail())


def _update_pipeline_stage(job_id: int, stage: int) -> None:
    """Update pipeline_stage on a SimulationJob row."""
    _run_async(_async_update_pipeline_stage(job_id, stage))


async def _async_update_pipeline_stage(job_id: int, stage: int) -> None:
    """Async impl of _update_pipeline_stage — safe to await from async callbacks.

    Also transitions status to RUNNING on the first real pipeline stage (>= 1).
    """
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return
    async with factory() as session:
        try:
            if stage >= 1:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET pipeline_stage = :stage, status = 'RUNNING' "
                        "WHERE id = :job_id"
                    ),
                    {"stage": stage, "job_id": job_id},
                )
            else:
                await session.execute(
                    text("UPDATE simulation_jobs SET pipeline_stage = :stage WHERE id = :job_id"),
                    {"stage": stage, "job_id": job_id},
                )
            await session.commit()
            logger.debug("Set pipeline_stage=%d for job %d", stage, job_id)
        except Exception as exc:
            logger.warning("Could not update pipeline_stage for job %d: %s", job_id, exc)


def _update_pod_id(job_id: int, pod_id: str, gpu_provider: str = "runpod") -> None:
    """Persist pod_id to the SimulationJob row immediately after GPU provisioning.

    Uses a sync connection to avoid asyncpg InterfaceError when the async pool
    is busy with concurrent operations (enrichment, heartbeat, etc.).
    """
    import os
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping pod_id update for job %d", job_id)
        return

    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs SET pod_id = :pod_id, status = 'PROVISIONING', "
                    "gpu_provider = :gpu_provider WHERE id = :job_id"
                ),
                {"pod_id": pod_id, "gpu_provider": gpu_provider, "job_id": job_id},
            )
            conn.commit()
            logger.info("Saved pod_id=%s for job %d (status → PROVISIONING)", pod_id, job_id)
        engine.dispose()
    except Exception as exc:
        logger.warning("Could not save pod_id for job %d: %s", job_id, exc)


async def _async_update_pod_id(job_id: int, pod_id: str, gpu_provider: str = "runpod") -> None:
    """Async impl of _update_pod_id — safe to await from async callbacks."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        logger.warning("DATABASE_URL not set; skipping pod_id update for job %d", job_id)
        return
    async with factory() as session:
        try:
            await session.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET pod_id = :pod_id, gpu_provider = :gpu_provider, status = 'PROVISIONING' "
                    "WHERE id = :job_id"
                ),
                {"pod_id": pod_id, "gpu_provider": gpu_provider, "job_id": job_id},
            )
            await session.commit()
            logger.info(
                "Saved pod_id=%s gpu_provider=%s for job %d (status → PROVISIONING)",
                pod_id,
                gpu_provider,
                job_id,
            )
        except Exception as exc:
            logger.warning("Could not save pod_id for job %d: %s", job_id, exc)


def _update_job_metadata(job_id: int, pod_id: str, provision_seconds: int | None = None, pipeline_seconds: int | None = None) -> None:
    """Persist pod_id and timing metadata to the SimulationJob row."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        logger.warning("DATABASE_URL not set; skipping metadata update for job %d", job_id)
        return

    async def _do_update():
        async with factory() as session:
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

    _run_async(_do_update())


def _update_heartbeat(job_id: int) -> None:
    """Update last_heartbeat timestamp on a SimulationJob row."""
    _run_async(_async_update_heartbeat(job_id))


async def _async_update_heartbeat(job_id: int) -> None:
    """Async impl of _update_heartbeat — safe to await from async callbacks."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return
    async with factory() as session:
        try:
            await session.execute(
                text(
                    "UPDATE simulation_jobs SET last_heartbeat = :now "
                    "WHERE id = :job_id"
                ),
                {"now": datetime.now(timezone.utc), "job_id": job_id},
            )
            await session.commit()
        except Exception as exc:
            logger.warning("Could not update heartbeat for job %d: %s", job_id, exc)


def _update_enrichment(job_id: int, enriched_text: str, citations_json: str) -> None:
    """Persist enrichment results to the SimulationJob row."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return

    async def _do_update():
        async with factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET enriched_seed = :enriched, enrichment_citations = :citations "
                        "WHERE id = :job_id"
                    ),
                    {"enriched": enriched_text, "citations": citations_json, "job_id": job_id},
                )
                await session.commit()
                logger.info("Saved enrichment for job %d (%d chars)", job_id, len(enriched_text))
            except Exception as exc:
                logger.warning("Could not save enrichment for job %d: %s", job_id, exc)

    _run_async(_do_update())


def _update_job_retry(job_id: int, retry_count: int) -> None:
    """Update retry_count and reset status to PROVISIONING for a job being retried."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return

    async def _do_update():
        async with factory() as session:
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

    _run_async(_do_update())
