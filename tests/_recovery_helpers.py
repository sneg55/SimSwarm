"""Shared helpers for recovery branch tests."""
from __future__ import annotations

from unittest.mock import MagicMock


class ConnCtx:
    """Mock for SQLAlchemy engine.connect() context manager."""
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


def mock_engine_with_rows(stale_rows, update_rowcount=1, single_connect=False):
    """Return (mock_engine, mock_conn).

    Conn.execute(SELECT) returns stale_rows for the main stale-job query;
    the REPORTING query always returns no rows; UPDATE/INSERT return rowcount.

    single_connect is kept for backward compat but ignored — the engine now
    always supports multiple connect() calls so the _recover_reporting_jobs
    path (which opens its own connection in the short-circuit branch) works.
    """
    mock_conn = MagicMock()

    def execute_side(stmt, params=None):
        sql = str(stmt)
        if "SELECT id, user_id, tier" in sql:
            return iter(stale_rows)
        if "status = 'REPORTING'" in sql:
            return iter([])  # no orphaned REPORTING jobs in tests
        return MagicMock(rowcount=update_rowcount)

    mock_conn.execute.side_effect = execute_side

    mock_engine = MagicMock()
    # Always provide enough connections; recovery may open 1 or 2 depending on path.
    mock_engine.connect.side_effect = [
        ConnCtx(mock_conn),
        ConnCtx(mock_conn),
        ConnCtx(mock_conn),
    ]
    return mock_engine, mock_conn
