"""Tests for pipeline.submit_job payload shape."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from saas.jobs.config import JobConfig
from saas.jobs.pipeline import submit_job


def _make_config(**overrides):
    base = dict(
        job_id=1, user_id="u1", seed_text="s", goal="g", tier="small",
        model_id="m", gpu_type="L40S", max_rounds=15, vllm_args="",
        llm_api_key="", openai_api_key="",
        neo4j_uri="", neo4j_user="", neo4j_password="",
        forecast_days=30, target_agents=5, upload_urls={"x": "y"},
    )
    base.update(overrides)
    return JobConfig(**base)


class TestSubmitJobPayload:
    @pytest.mark.asyncio
    async def test_markets_config_included_when_set(self):
        client = MagicMock()
        resp = MagicMock(status_code=200)
        client.post = AsyncMock(return_value=resp)
        cfg = _make_config(markets_config=[
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": ""},
        ])
        await submit_job("http://worker", cfg, client)
        called_kwargs = client.post.call_args.kwargs
        body = called_kwargs["json"]
        assert body["markets_config"] == [
            {"question": "Q?", "initial_price_yes": 0.5, "rationale": ""},
        ]

    @pytest.mark.asyncio
    async def test_markets_config_none_when_unset(self):
        client = MagicMock()
        resp = MagicMock(status_code=200)
        client.post = AsyncMock(return_value=resp)
        cfg = _make_config()
        await submit_job("http://worker", cfg, client)
        body = client.post.call_args.kwargs["json"]
        assert body["markets_config"] is None
