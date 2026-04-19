"""Shared helpers for e2e tests."""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock


def mock_celery_delay():
    """Return a context manager that patches the Temporal dispatch in saas.jobs.api."""
    fake_handle = MagicMock()
    fake_handle.id = "sim-mock-id"
    fake_handle.result_run_id = "run-mock"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    return patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client))
