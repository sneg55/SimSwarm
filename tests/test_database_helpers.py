"""Tests for saas.database init_db and get_session error path."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import saas.database as db_mod


async def test_init_db_sets_engine_and_factories():
    # Use in-memory sqlite; reset globals after
    saved = (db_mod._engine, db_mod._session_factory, db_mod.async_session_factory)
    try:
        db_mod.init_db("sqlite+aiosqlite://")
        assert db_mod._engine is not None
        assert db_mod._session_factory is not None
        assert db_mod.async_session_factory is db_mod._session_factory
    finally:
        if db_mod._engine is not None:
            await db_mod._engine.dispose()
        db_mod._engine, db_mod._session_factory, db_mod.async_session_factory = saved


async def test_get_session_yields_session_and_rolls_back_on_error():
    saved = (db_mod._engine, db_mod._session_factory, db_mod.async_session_factory)
    try:
        db_mod.init_db("sqlite+aiosqlite://")
        gen = db_mod.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)

        # Trigger the rollback/raise branch by sending an exception into the generator
        with pytest.raises(RuntimeError, match="boom"):
            await gen.athrow(RuntimeError("boom"))
    finally:
        if db_mod._engine is not None:
            await db_mod._engine.dispose()
        db_mod._engine, db_mod._session_factory, db_mod.async_session_factory = saved


async def test_get_session_closes_cleanly_on_success():
    saved = (db_mod._engine, db_mod._session_factory, db_mod.async_session_factory)
    try:
        db_mod.init_db("sqlite+aiosqlite://")
        gen = db_mod.get_session()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
    finally:
        if db_mod._engine is not None:
            await db_mod._engine.dispose()
        db_mod._engine, db_mod._session_factory, db_mod.async_session_factory = saved
