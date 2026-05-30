"""Tests for pre-GPU activities (enrichment, market derivation).

Activities are plain async functions; tests call them directly without
a Temporal runtime. The Temporal @activity.defn decorator is a no-op when
called outside a worker context.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_enrich_seed_returns_concatenated_text_on_success():
    from saas.workflows.activities.pre_gpu import enrich_seed

    fake_result = MagicMock(summary="Background research body", citations=[{"url": "x"}])

    with patch("saas.jobs.enrichment.enrich_seed", return_value=fake_result) as mock_enrich, \
         patch("saas.jobs.persistence._update_enrichment") as mock_update:
        result = await enrich_seed("seed text", "goal text", job_id=42)

    mock_enrich.assert_called_once_with("seed text", "goal text")
    mock_update.assert_called_once()
    assert "Background research body" in result
    assert "seed text" in result


@pytest.mark.asyncio
async def test_enrich_seed_returns_original_on_miss():
    from saas.workflows.activities.pre_gpu import enrich_seed

    with patch("saas.jobs.enrichment.enrich_seed", return_value=None), \
         patch("saas.jobs.persistence._update_enrichment") as mock_update:
        result = await enrich_seed("seed text", "goal text", job_id=42)

    mock_update.assert_not_called()
    assert result == "seed text"


@pytest.mark.asyncio
async def test_derive_markets_persists_and_returns_list():
    from saas.workflows.activities.pre_gpu import derive_markets

    fake_derivation = {
        "source": "llm",
        "markets": [
            {"name": "M1", "stance": "yes", "question": "q1"},
            {"name": "M2", "stance": "no", "question": "q2"},
        ],
    }

    with patch("saas.jobs.market_derivation.derive_markets", return_value=fake_derivation) as mock_derive, \
         patch("saas.jobs.persistence._update_markets_config") as mock_update:
        result = await derive_markets(goal="g", enriched_seed="s", tier="medium", job_id=77)

    mock_derive.assert_called_once_with(goal="g", enriched_seed="s", tier="medium")
    mock_update.assert_called_once_with(77, fake_derivation["markets"])
    assert len(result) == 2
    assert result[0]["name"] == "M1"
