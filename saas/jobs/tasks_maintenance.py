"""Maintenance Celery tasks for SimSwarm (housekeeping, pruning)."""
from __future__ import annotations

import logging
import os

from saas.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="fishcloud.prune_error_events")
def prune_error_events() -> dict:
    """Delete error_events rows older than 30 days."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("prune_error_events: DATABASE_URL not set, skipping")
        return {"deleted": 0}

    sync_url = (
        database_url
        .replace("+asyncpg", "")
        .replace("postgresql://", "postgresql+psycopg2://")
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("DELETE FROM error_events WHERE timestamp < :cutoff"),
                {"cutoff": cutoff},
            )
            conn.commit()
            deleted = result.rowcount
        logger.info("prune_error_events: deleted=%d rows older than 30d", deleted)
        return {"deleted": deleted}
    finally:
        engine.dispose()
