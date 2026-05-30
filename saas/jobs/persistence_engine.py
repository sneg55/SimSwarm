"""Shared DB engine/session factory helpers for persistence modules."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level lazy async engine — avoids creating a new engine per helper call
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


def _get_sync_engine():
    """Return a fresh sync SQLAlchemy engine using psycopg2."""
    from sqlalchemy import create_engine

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None
    sync_url = database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(sync_url)
