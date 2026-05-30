"""Coverage for saas.jobs.tasks_maintenance.prune_error_events."""
from unittest.mock import MagicMock, patch


def test_prune_no_db_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    from saas.jobs.tasks_maintenance import prune_error_events
    assert prune_error_events() == {"deleted": 0}


def test_prune_deletes_rows(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result
    mock_conn.commit = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_conn
    ctx.__exit__.return_value = False

    mock_engine = MagicMock()
    mock_engine.connect.return_value = ctx
    mock_engine.dispose = MagicMock()

    with patch("sqlalchemy.create_engine", return_value=mock_engine):
        from saas.jobs.tasks_maintenance import prune_error_events
        result = prune_error_events()

    assert result == {"deleted": 5}
    mock_engine.dispose.assert_called_once()


def test_prune_converts_asyncpg_url(monkeypatch):
    """Ensures +asyncpg is stripped and postgresql:// becomes postgresql+psycopg2://."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")

    seen = {}

    def fake_create_engine(url):
        seen["url"] = url
        e = MagicMock()
        ctx = MagicMock()
        ctx.__enter__.return_value = MagicMock(
            execute=MagicMock(return_value=MagicMock(rowcount=0)),
            commit=MagicMock(),
        )
        ctx.__exit__.return_value = False
        e.connect.return_value = ctx
        return e

    with patch("sqlalchemy.create_engine", side_effect=fake_create_engine):
        from saas.jobs.tasks_maintenance import prune_error_events
        prune_error_events()

    assert "psycopg2" in seen["url"]
    assert "asyncpg" not in seen["url"]
