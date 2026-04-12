"""Tests for saas.workers.utils._run_async and _get_gpu_provider."""
import os
from unittest.mock import patch

from saas.workers.utils import _run_async, _get_gpu_provider


def test_run_async_no_running_loop_uses_asyncio_run():
    async def coro():
        return 7
    assert _run_async(coro()) == 7


async def test_run_async_from_running_loop_uses_threadpool():
    # This test itself runs inside pytest-asyncio's event loop
    async def coro():
        return 99
    result = _run_async(coro())
    assert result == 99


def test_run_async_propagates_exception():
    async def boom():
        raise ValueError("oops")
    import pytest
    with pytest.raises(ValueError, match="oops"):
        _run_async(boom())


def test_get_gpu_provider_returns_runpod_provider():
    with patch.dict(os.environ, {"RUNPOD_API_KEY": "fake-key"}):
        provider = _get_gpu_provider()
        assert provider.api_key == "fake-key"


def test_get_gpu_provider_without_env_var():
    env = os.environ.copy()
    env.pop("RUNPOD_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        provider = _get_gpu_provider()
        assert provider.api_key == ""
