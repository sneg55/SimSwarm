"""Credit refund logic for failed jobs."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from saas.workers.utils import _run_async

logger = logging.getLogger(__name__)


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
                        "INSERT INTO credit_entries "
                        "(user_id, amount, description, job_id, created_at) "
                        "VALUES (:user_id, :amount, :description, :job_id, :created_at)"
                    ),
                    {
                        "user_id": user_id,
                        "amount": credits,
                        "description": f"Refund for failed job {job_id}",
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
