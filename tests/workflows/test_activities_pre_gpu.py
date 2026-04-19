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
