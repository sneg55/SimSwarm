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

    Conn.execute(SELECT) returns stale_rows; UPDATE/INSERT return rowcount.
    """
    mock_conn = MagicMock()

    def execute_side(stmt, params=None):
        sql = str(stmt)
        if "SELECT id, user_id, tier" in sql:
            return iter(stale_rows)
        return MagicMock(rowcount=update_rowcount)

    mock_conn.execute.side_effect = execute_side

    mock_engine = MagicMock()
    if single_connect:
        mock_engine.connect.side_effect = [ConnCtx(mock_conn)]
    else:
        mock_engine.connect.side_effect = [ConnCtx(mock_conn), ConnCtx(mock_conn)]
    return mock_engine, mock_conn
