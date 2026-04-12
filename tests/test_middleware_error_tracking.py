"""Tests for saas.middleware.error_tracking.log_error_event."""
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from saas.middleware.error_tracking import log_error_event
from saas.models.base import Base
import saas.database as db_mod
# Trigger model registration
from saas.jobs.models import ErrorEvent  # noqa: F401


def _make_request(path: str = "/api/foo"):
    req = MagicMock()
    req.url.path = path
    return req


async def test_log_error_event_writes_to_db():
    # Set up a real in-memory async sqlite and point async_session_factory to it
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    saved = db_mod.async_session_factory
    db_mod.async_session_factory = factory
    try:
        req = _make_request("/api/thing")
        await log_error_event(req, ValueError("oops"))

        async with factory() as s:
            rows = (await s.execute(__import__("sqlalchemy").text("SELECT message, request_path FROM error_events"))).all()
        assert len(rows) == 1
        assert "oops" in rows[0][0]
        assert rows[0][1] == "/api/thing"
    finally:
        db_mod.async_session_factory = saved
        await engine.dispose()


async def test_log_error_event_no_factory_is_silent():
    saved = db_mod.async_session_factory
    db_mod.async_session_factory = None
    try:
        # Should not raise
        await log_error_event(_make_request(), RuntimeError("x"))
    finally:
        db_mod.async_session_factory = saved


async def test_log_error_event_swallows_db_errors():
    # Factory raises on use — the middleware must silently swallow.
    saved = db_mod.async_session_factory

    class BrokenFactory:
        def __call__(self):
            raise RuntimeError("db blown up")

    db_mod.async_session_factory = BrokenFactory()
    try:
        await log_error_event(_make_request(), Exception("original"))  # must not raise
    finally:
        db_mod.async_session_factory = saved
