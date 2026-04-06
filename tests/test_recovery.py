"""Tests for saas/workers/recovery.py."""
from datetime import datetime, timezone, timedelta

import pytest

from saas.jobs.recovery import _is_stale


def test_recovery_raises_when_no_database_url(monkeypatch):
    """recover_stale_jobs must raise RuntimeError when DATABASE_URL is unset."""
    monkeypatch.setenv("DATABASE_URL", "")

    from saas.jobs.recovery import recover_stale_jobs

    with pytest.raises(RuntimeError, match="DATABASE_URL not set"):
        recover_stale_jobs()


def test_recovery_stale_heartbeat_dead_pod():
    """Job with heartbeat >5 min ago and dead pod should be stale."""
    old_hb = datetime.now(timezone.utc) - timedelta(minutes=6)
    assert _is_stale(
        last_heartbeat=old_hb,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        pod_alive=False,
        tier_timeout=2700,
    ) is True


def test_recovery_fresh_heartbeat_alive_pod():
    """Job with recent heartbeat and alive pod should NOT be stale."""
    fresh_hb = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert _is_stale(
        last_heartbeat=fresh_hb,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        pod_alive=True,
        tier_timeout=2700,
    ) is False


def test_recovery_stale_heartbeat_alive_pod_15min():
    """Job with heartbeat >15 min ago should be stale even if pod is alive."""
    old_hb = datetime.now(timezone.utc) - timedelta(minutes=16)
    assert _is_stale(
        last_heartbeat=old_hb,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        pod_alive=True,
        tier_timeout=2700,
    ) is True


def test_recovery_no_heartbeat_legacy_fallback():
    """Job with no heartbeat uses created_at + tier_timeout fallback."""
    old_created = datetime.now(timezone.utc) - timedelta(minutes=60)
    assert _is_stale(
        last_heartbeat=None,
        created_at=old_created,
        pod_alive=False,
        tier_timeout=2700,
    ) is True


def test_recovery_no_heartbeat_within_timeout():
    """Job with no heartbeat but within tier_timeout should NOT be stale."""
    recent_created = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert _is_stale(
        last_heartbeat=None,
        created_at=recent_created,
        pod_alive=True,
        tier_timeout=2700,
    ) is False
