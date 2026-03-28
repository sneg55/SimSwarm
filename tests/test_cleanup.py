"""Tests for saas/workers/cleanup.py."""
import pytest


def test_cleanup_raises_when_no_runpod_api_key(monkeypatch):
    """cleanup_orphaned_pods must raise RuntimeError when RUNPOD_API_KEY is unset."""
    monkeypatch.setenv("RUNPOD_API_KEY", "")

    from saas.workers.cleanup import cleanup_orphaned_pods

    with pytest.raises(RuntimeError, match="RUNPOD_API_KEY not set"):
        cleanup_orphaned_pods()
