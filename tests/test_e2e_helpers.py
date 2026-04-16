"""Shared helpers for e2e tests."""
from __future__ import annotations

from unittest.mock import patch, MagicMock


def mock_celery_delay():
    """Return a context manager that patches run_simulation_task.delay."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-mock"
    return patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task)
