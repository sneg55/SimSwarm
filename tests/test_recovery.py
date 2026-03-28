"""Tests for saas/workers/recovery.py."""
import pytest


def test_recovery_raises_when_no_database_url(monkeypatch):
    """recover_stale_jobs must raise RuntimeError when DATABASE_URL is unset."""
    monkeypatch.setenv("DATABASE_URL", "")

    from saas.workers.recovery import recover_stale_jobs

    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        recover_stale_jobs()
