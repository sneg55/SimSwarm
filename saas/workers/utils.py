"""Shared utility helpers for the workers package."""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def _run_async(coro) -> object:
    """
    Run an async coroutine from a synchronous Celery worker context.

    Celery workers typically run without a running event loop, so
    ``asyncio.run()`` works.  When called from a thread that already has a
    running loop (e.g. pytest-asyncio tests), we submit the work to a
    dedicated thread pool instead to avoid the "cannot run nested event loop"
    error.
    """
    try:
        asyncio.get_running_loop()  # noqa: F841 — we just check if one exists
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)

    # A running loop exists; schedule the coroutine in a separate thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _get_gpu_provider():
    """Return the RunPod GPU provider."""
    from saas.gpu.runpod_provider import RunPodProvider

    return RunPodProvider(api_key=os.getenv("RUNPOD_API_KEY", ""))
