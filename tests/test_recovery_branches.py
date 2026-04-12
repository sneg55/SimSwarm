"""Tests for recovery._check_pod_status and _is_stale edge cases."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import httpx

from saas.jobs import recovery


def test_check_pod_status_running():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "running"}
    with patch("httpx.get", return_value=resp):
        assert recovery._check_pod_status("pod-1") == "running"


def test_check_pod_status_idle():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "idle"}
    with patch("httpx.get", return_value=resp):
        assert recovery._check_pod_status("pod-1") == "idle"


def test_check_pod_status_non_200():
    resp = MagicMock(status_code=500)
    with patch("httpx.get", return_value=resp):
        assert recovery._check_pod_status("pod-1") == "unreachable"


def test_check_pod_status_missing_key_returns_unknown():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {}
    with patch("httpx.get", return_value=resp):
        assert recovery._check_pod_status("pod-1") == "unknown"


def test_check_pod_status_raises_exception():
    with patch("httpx.get", side_effect=httpx.ConnectError("boom")):
        assert recovery._check_pod_status("pod-1") == "unreachable"


def test_is_stale_accepts_naive_heartbeat():
    naive_hb = datetime.utcnow() - timedelta(minutes=1)
    assert recovery._is_stale(
        last_heartbeat=naive_hb,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        pod_alive=True,
        tier_timeout=2700,
    ) is False


def test_is_stale_heartbeat_recent_pod_dead_not_stale():
    hb = datetime.now(timezone.utc) - timedelta(minutes=2)
    assert recovery._is_stale(
        last_heartbeat=hb,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        pod_alive=False,
        tier_timeout=2700,
    ) is False


def test_is_stale_no_heartbeat_naive_created_at():
    naive_created = datetime.utcnow() - timedelta(hours=10)
    assert recovery._is_stale(
        last_heartbeat=None,
        created_at=naive_created,
        pod_alive=True,
        tier_timeout=2700,
    ) is True
