"""Tests for the submit_and_poll activity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.workflows.types import SimParams


def _params(job_id: int = 1) -> SimParams:
    return SimParams(
        job_id=job_id, user_id="u", seed_text="s", goal="g",
        tier="small", model_id="m", gpu_type="L40S", max_rounds=15,
        vllm_args="", llm_api_key="k",
    )


@pytest.mark.asyncio
async def test_submit_and_poll_resumes_when_pod_already_running():
    """If /status shows running, don't re-POST /job — hand off to polling."""
    from saas.workflows.activities.pipeline import submit_and_poll

    status_resp = MagicMock(status_code=200)
    status_resp.json = MagicMock(return_value={"status": "running"})

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=status_resp)
    fake_client.post = AsyncMock()  # should NOT be called
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    async def fake_poll(*args, **kwargs):
        return {
            "report": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True, "pod_id": "pod-1",
        }

    with patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.jobs.pipeline.poll_until_complete", side_effect=fake_poll), \
         patch("saas.jobs.persistence._transition_to_running"):
        result = await submit_and_poll("pod-1", _params(), markets=[])

    fake_client.post.assert_not_called()
    assert result["sim_data_uploaded"] is True


@pytest.mark.asyncio
async def test_submit_and_poll_submits_when_pod_idle():
    from saas.workflows.activities.pipeline import submit_and_poll

    status_resp = MagicMock(status_code=200)
    status_resp.json = MagicMock(return_value={"status": "idle"})
    submit_resp = MagicMock(status_code=200)

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=status_resp)
    fake_client.post = AsyncMock(return_value=submit_resp)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    async def fake_poll(*args, **kwargs):
        return {
            "report": "", "chat_log": "[]", "graph_data": "{}", "structured": "{}",
            "sim_data_uploaded": True, "pod_id": "pod-2",
        }

    with patch("httpx.AsyncClient", return_value=fake_client), \
         patch("saas.jobs.pipeline.poll_until_complete", side_effect=fake_poll), \
         patch("saas.jobs.persistence._transition_to_running"):
        await submit_and_poll("pod-2", _params(job_id=7), markets=[{"name": "M"}])

    fake_client.post.assert_called_once()
    post_url = fake_client.post.call_args[0][0]
    assert post_url.endswith("/job")
