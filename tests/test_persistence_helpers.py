"""Tests for saas.jobs.persistence_engine."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from saas.jobs import persistence_engine


# ---------------------------------------------------------------------------
# persistence_engine
# ---------------------------------------------------------------------------

def test_get_worker_session_factory_returns_none_without_db_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    # Reset the module-level cache
    monkeypatch.setattr(persistence_engine, "_session_factory", None)
    monkeypatch.setattr(persistence_engine, "_engine", None)
    assert persistence_engine._get_worker_session_factory() is None


def test_get_worker_session_factory_caches(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setattr(persistence_engine, "_session_factory", None)
    monkeypatch.setattr(persistence_engine, "_engine", None)

    try:
        factory1 = persistence_engine._get_worker_session_factory()
        assert factory1 is not None
        factory2 = persistence_engine._get_worker_session_factory()
        assert factory1 is factory2
    finally:
        # Cleanup so cache doesn't leak into other tests
        monkeypatch.setattr(persistence_engine, "_session_factory", None)
        monkeypatch.setattr(persistence_engine, "_engine", None)


def test_get_sync_engine_returns_none_without_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert persistence_engine._get_sync_engine() is None


def test_get_sync_engine_rewrites_asyncpg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pw@host/db")
    with patch("sqlalchemy.create_engine") as mock_create:
        mock_create.return_value = MagicMock(name="engine")
        result = persistence_engine._get_sync_engine()
    assert result is not None
    call_url = mock_create.call_args.args[0]
    assert "+asyncpg" not in call_url
    assert "postgresql+psycopg2://" in call_url


def test_get_sync_engine_sqlite_passthrough(monkeypatch):
    """Non-postgres URLs should still produce an engine via create_engine."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    eng = persistence_engine._get_sync_engine()
    assert eng is not None
    eng.dispose()
