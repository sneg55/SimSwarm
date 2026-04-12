"""Tests for saas.jobs.persistence (shim helpers) and saas.jobs.persistence_engine."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


from saas.jobs import persistence, persistence_engine


# ---------------------------------------------------------------------------
# _extract_key_insight
# ---------------------------------------------------------------------------

def test_extract_key_insight_empty_string():
    assert persistence._extract_key_insight("") is None


def test_extract_key_insight_none_like():
    assert persistence._extract_key_insight(None) is None  # type: ignore[arg-type]


def test_extract_key_insight_only_headings():
    """Returns None if no line has >30 chars of non-heading content."""
    report = "# Big Heading\n## Subheading\nshort"
    assert persistence._extract_key_insight(report) is None


def test_extract_key_insight_finds_first_long_line():
    report = (
        "# Title\n"
        "short line\n"
        "This is a sufficiently long substantive line about outcomes.\n"
        "## Section"
    )
    insight = persistence._extract_key_insight(report)
    assert insight is not None
    assert "sufficiently long" in insight


def test_extract_key_insight_truncates_to_200():
    long_line = "A" * 500
    report = f"# Title\n{long_line}"
    insight = persistence._extract_key_insight(report)
    assert insight is not None
    assert len(insight) == 200


# ---------------------------------------------------------------------------
# _claim_resume / _release_resume — engine=None branches
# ---------------------------------------------------------------------------

def test_claim_resume_returns_false_when_engine_none():
    with patch("saas.jobs.persistence._get_sync_engine", return_value=None):
        assert persistence._claim_resume(1, "tid") is False


def test_claim_resume_exception_returns_false():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("boom")
    with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
        assert persistence._claim_resume(1, "tid") is False
    mock_engine.dispose.assert_called_once()


def test_release_resume_noop_when_engine_none():
    with patch("saas.jobs.persistence._get_sync_engine", return_value=None):
        persistence._release_resume(1)  # no raise


def test_release_resume_exception_swallowed():
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = RuntimeError("boom")
    with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
        persistence._release_resume(1)
    mock_engine.dispose.assert_called_once()


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
