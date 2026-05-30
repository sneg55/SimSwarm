"""status_callback firing in poll_until_complete.

Guards the PROVISIONING → RUNNING transition that was missing before the
2026-04-19 task-redelivery hardening work.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.jobs import pipeline


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
        yield


def _completed_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "status": "completed", "report": "r", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}", "sim_data_uploaded": True,
    }
    return r


def _log_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"lines": []}
    return r


class _Cfg:
    job_id = 1
    timeout_seconds = 30
    max_rounds = 5


async def test_fires_once_on_first_running_response():
    """Multiple `status: running` polls fire the callback exactly once."""
    running = MagicMock()
    running.status_code = 200
    running.json.return_value = {"status": "running"}
    completed = _completed_response()
    log_resp = _log_response()

    responses = [running, running, completed]

    def side(url, **kw):
        if "/logs" in url:
            return log_resp
        if "/partial_chat" in url:
            pc = MagicMock()
            pc.status_code = 200
            pc.json.return_value = {"messages": []}
            return pc
        return responses.pop(0) if responses else completed

    client = AsyncMock()
    client.get.side_effect = side

    calls = []

    async def status_cb(jid, status):
        calls.append((jid, status))

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
            status_callback=status_cb,
        )

    assert calls == [(1, "RUNNING")]


async def test_skips_callback_when_status_never_running():
    """Jobs that go provisioning→completed without reporting `running`
    do not fire the callback."""
    completed = _completed_response()
    log_resp = _log_response()

    def side(url, **kw):
        if "/logs" in url:
            return log_resp
        return completed

    client = AsyncMock()
    client.get.side_effect = side

    calls = []

    async def status_cb(jid, status):
        calls.append((jid, status))

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
            status_callback=status_cb,
        )
    assert calls == []


async def test_swallows_status_callback_exception():
    """A failing status_callback must not abort the poll loop."""
    running = MagicMock()
    running.status_code = 200
    running.json.return_value = {"status": "running"}
    completed = _completed_response()
    log_resp = _log_response()

    responses = [running, completed]

    def side(url, **kw):
        if "/logs" in url:
            return log_resp
        if "/partial_chat" in url:
            pc = MagicMock()
            pc.status_code = 200
            pc.json.return_value = {"messages": []}
            return pc
        return responses.pop(0) if responses else completed

    client = AsyncMock()
    client.get.side_effect = side

    async def status_cb(jid, status):
        raise RuntimeError("cb boom")

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
            status_callback=status_cb,
        )
    assert result["status"] == "completed"
