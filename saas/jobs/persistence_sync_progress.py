"""Sync (psycopg2) progress/metadata write helpers — safe to call from Celery tasks."""
from __future__ import annotations

import logging

from saas.jobs.persistence_engine import _get_sync_engine

logger = logging.getLogger(__name__)


def _update_pipeline_stage_sync(job_id: int, stage: int) -> None:
    """Update pipeline_stage and set status to RUNNING (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping pipeline_stage update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs SET pipeline_stage = :stage, status = 'RUNNING' "
                    "WHERE id = :job_id AND status != 'COMPLETED'"
                ),
                {"stage": stage, "job_id": job_id},
            )
            conn.commit()
            logger.debug("Set pipeline_stage=%d for job %d", stage, job_id)
    except Exception as exc:
        logger.warning("Could not update pipeline_stage for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_heartbeat_sync(job_id: int) -> None:
    """Update last_heartbeat timestamp (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping heartbeat update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET last_heartbeat = now() WHERE id = :job_id"),
                {"job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not update heartbeat for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_live_status_sync(job_id: int, live_status: dict) -> None:
    """Write live_status JSONB for a running job (sync, for Celery)."""
    import json
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping live_status update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET live_status = CAST(:live_status AS JSONB) "
                    "WHERE id = :job_id"
                ),
                {"live_status": json.dumps(live_status), "job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not update live_status for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_pod_id(job_id: int, pod_id: str, gpu_provider: str = "runpod") -> None:
    """Persist pod_id to the SimulationJob row immediately after GPU provisioning."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping pod_id update for job %d", job_id)
        return
    try:
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
    except Exception as exc:
        logger.warning("Could not save pod_id for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_sim_data_available(job_id: int, available: bool) -> None:
    """Mark whether rich simulation data was uploaded to MinIO."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping sim_data_available update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET sim_data_available = :available WHERE id = :job_id"),
                {"available": available, "job_id": job_id},
            )
            conn.commit()
            logger.info("Set sim_data_available=%s for job %d", available, job_id)
    except Exception as exc:
        logger.warning("Could not update sim_data_available for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_enrichment_sync(job_id: int, enriched_text: str, citations_json: str) -> None:
    """Persist enrichment results to the SimulationJob row (sync, for Celery)."""
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping enrichment save for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET enriched_seed = :enriched, enrichment_citations = :citations "
                    "WHERE id = :job_id"
                ),
                {"enriched": enriched_text, "citations": citations_json, "job_id": job_id},
            )
            conn.commit()
            logger.info("Saved enrichment for job %d (%d chars)", job_id, len(enriched_text))
    except Exception as exc:
        logger.warning("Could not save enrichment for job %d: %s", job_id, exc)
    finally:
        engine.dispose()


def _update_markets_config_sync(job_id: int, markets: list[dict] | None) -> None:
    """Persist derived markets_config to the SimulationJob row (sync, for Celery).

    markets=None clears the column. Matches the silent-fail pattern used by the
    other persistence helpers: any DB error logs a warning and returns.
    """
    import json as _json
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping markets_config save for job %d", job_id)
        return
    try:
        payload = _json.dumps(markets) if markets is not None else None
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE simulation_jobs SET markets_config = :markets WHERE id = :job_id"),
                {"markets": payload, "job_id": job_id},
            )
            conn.commit()
            count = len(markets) if markets else 0
            logger.info("Saved markets_config for job %d (%d markets)", job_id, count)
    except Exception as exc:
        logger.warning("Could not save markets_config for job %d: %s", job_id, exc)
    finally:
        engine.dispose()
