"""Edge cases in submit_job's "already running" detection.

Sim 154 (2026-05-18) failed because the pod_unreachable retry's
submit_and_poll re-entry POSTed to /job, worker returned 409 with an
empty error body, and the old text-match check ("already running" in
error_msg) didn't fire on empty strings — workflow died despite the
job actually being alive on the pod. The fix now treats any 409 as
"already running" semantically, plus empty error bodies on any 4xx,
since both indicate the worker can't accept a new job (either there's
one running or it's in some indeterminate state where bailing into
poll is safer than failing the sim).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.jobs.worker_http import submit_job


class _Cfg:
    seed_text = "s"
    goal = "g"
    max_rounds = 10
    forecast_days = None
    target_agents = 5
    upload_urls = None
    markets_config = None
    timeout_seconds = 3600


@pytest.mark.asyncio
async def test_409_with_empty_body_is_treated_as_already_running():
    resp = MagicMock(status_code=409)
    resp.json.return_value = {"error": ""}
    resp.text = ""

    client = AsyncMock()
    client.post.return_value = resp

    # Should NOT raise.
    await submit_job("http://w", _Cfg(), client)


@pytest.mark.asyncio
async def test_409_with_unrelated_message_is_treated_as_already_running():
    """409 is semantically Conflict — even if the message doesn't say
    'already running', the worker is signalling it can't accept the POST."""
    resp = MagicMock(status_code=409)
    resp.json.return_value = {"error": "Conflict — see /logs"}
    resp.text = "Conflict"

    client = AsyncMock()
    client.post.return_value = resp

    await submit_job("http://w", _Cfg(), client)


@pytest.mark.asyncio
async def test_500_with_real_error_still_raises():
    """A real server-side error must propagate — only 409 + empty bodies
    are treated as soft conflicts."""
    resp = MagicMock(status_code=500)
    resp.json.return_value = {"error": "vLLM crashed"}
    resp.text = "vLLM crashed"

    client = AsyncMock()
    client.post.return_value = resp

    with pytest.raises(RuntimeError, match="vLLM crashed"):
        await submit_job("http://w", _Cfg(), client)
