"""Shared fixtures for workflow tests: time-skipping Temporal environment."""
from __future__ import annotations

import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment


@pytest_asyncio.fixture
async def temporal_env():
    """Time-skipping Temporal environment — no external server needed."""
    env = await WorkflowEnvironment.start_time_skipping()
    try:
        yield env
    finally:
        await env.shutdown()
