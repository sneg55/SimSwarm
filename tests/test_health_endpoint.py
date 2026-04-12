"""Tests for saas.health — exercises the 'disconnected' branch."""
from unittest.mock import AsyncMock, MagicMock

from saas.health import health


async def test_health_returns_connected_on_success():
    session = MagicMock()
    session.execute = AsyncMock(return_value=None)
    result = await health(session=session)
    assert result.status == "ok"
    assert result.database == "connected"
    assert result.version


async def test_health_returns_disconnected_when_query_fails():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=Exception("db down"))
    result = await health(session=session)
    assert result.status == "ok"
    assert result.database == "disconnected"
