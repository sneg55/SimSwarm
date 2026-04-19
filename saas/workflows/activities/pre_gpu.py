"""Pre-GPU activities: seed enrichment and market derivation.

Both activities are thin wrappers around existing saas.jobs.* implementations.
They exist as activities so the workflow can apply Temporal retry policies
and persist progress across worker restarts.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn(name="fishcloud.enrich_seed")
async def enrich_seed(seed_text: str, goal: str, job_id: int) -> str:
    """Enrich seed with xAI search; return concatenated text.

    On enrichment miss, returns the original seed_text unchanged (fail-soft).
    Side-effect: writes enrichment summary + citations to simulation_jobs row.
    """
    from saas.jobs.enrichment import enrich_seed as _enrich
    from saas.jobs.persistence import _update_enrichment

    result = _enrich(seed_text, goal)
    if result is None:
        logger.warning("activity.enrich_seed.miss job_id=%d", job_id)
        return seed_text

    _update_enrichment(job_id, result.summary, json.dumps(result.citations))
    return seed_text + "\n\n--- Background Research ---\n" + result.summary


@activity.defn(name="fishcloud.derive_markets")
async def derive_markets(
    goal: str, enriched_seed: str, tier: str, job_id: int,
) -> list[dict[str, Any]]:
    """Derive 3–5 prediction markets from seed + goal.

    Side-effect: writes markets_config JSON to simulation_jobs row.
    Fails soft: the underlying _derive always returns at least one market.
    """
    from saas.jobs.market_derivation import derive_markets as _derive
    from saas.jobs.persistence import _update_markets_config

    derivation = _derive(goal=goal, enriched_seed=enriched_seed, tier=tier)
    markets = derivation["markets"]
    _update_markets_config(job_id, markets)
    logger.info(
        "activity.derive_markets.ok job_id=%d source=%s count=%d",
        job_id, derivation["source"], len(markets),
    )
    return markets
