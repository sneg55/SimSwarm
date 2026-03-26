import pytest
from sqlalchemy import text


async def test_db_connection(db_engine):
    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


async def test_tables_created(db_engine):
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}
        assert "simulation_jobs" in tables
        assert "model_routing" in tables
