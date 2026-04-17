"""Derive prediction markets from a goal + enriched seed using xAI Grok.

Called from the Celery pipeline after enrichment, before the GPU pod provisions.
Output is persisted on SimulationJob.markets_config and forwarded to the pod so
the market env has markets to trade on.

Contract: always returns a non-empty list. Falls back to a single market built
from the goal itself if the LLM call fails, returns malformed JSON, or yields
zero valid markets after validation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DERIVATION_SOURCE_LLM = "llm"
DERIVATION_SOURCE_FALLBACK = "fallback_goal"

TIER_MARKET_CAPS = {"small": 3, "medium": 4, "large": 5}
_QUESTION_MAX_LEN = 120
_PRICE_MIN = 0.05
_PRICE_MAX = 0.95
_LLM_TIMEOUT_SECONDS = 20


def _build_client():
    """Return an OpenAI-compatible xAI client, or None if creds are missing.

    Mirrors the pattern in saas.jobs.enrichment.enrich_seed.
    """
    api_key = os.getenv("XAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    except Exception as exc:
        logger.warning("market_derivation: could not build xAI client: %s", exc)
        return None


def _build_prompt(goal: str, enriched_seed: str, cap: int) -> str:
    return (
        "You are a prediction market designer for an agent-based simulation.\n"
        f"Given a goal, derive up to {cap} binary (YES/NO) markets that collectively\n"
        "capture the resolution space of that goal. Markets should be:\n"
        "  - mutually informative (not trivially redundant)\n"
        "  - phrased with clear resolution criteria\n"
        "  - at most 120 characters per question\n\n"
        f"GOAL: {goal}\n\n"
        f"SEED CONTEXT:\n{enriched_seed[:3000]}\n\n"
        "Return ONLY a JSON object (no prose, no code fences) of this shape:\n"
        "{\n"
        '  "markets": [\n'
        '    {"question": "...", "initial_price_yes": 0.50, "rationale": "why this price"}\n'
        "  ]\n"
        "}\n"
        "initial_price_yes must be between 0.05 and 0.95 — do not use 0 or 1.\n"
    )


def _call_llm(goal: str, enriched_seed: str, cap: int) -> str | None:
    client = _build_client()
    if client is None:
        return None
    try:
        resp = client.responses.create(
            model="grok-4-fast-non-reasoning",
            input=_build_prompt(goal, enriched_seed, cap),
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        return resp.output_text or ""
    except Exception as exc:
        logger.warning("market_derivation: LLM call failed: %s", exc)
        return None


def _parse_raw(raw: str) -> list[dict[str, Any]] | None:
    """Extract the `markets` list from raw LLM output. Returns None on any parse issue."""
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    markets = data.get("markets")
    if not isinstance(markets, list):
        return None
    return markets


def _validate(raw_markets: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Validate + dedupe + tier-cap. Returns a possibly-empty list."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for m in raw_markets:
        if not isinstance(m, dict):
            continue
        q = m.get("question")
        if not isinstance(q, str):
            continue
        q = q.strip()
        if not q or len(q) > _QUESTION_MAX_LEN:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        price = m.get("initial_price_yes", 0.5)
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0.5
        price = max(_PRICE_MIN, min(_PRICE_MAX, price))
        rationale = m.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = ""
        out.append({
            "question": q,
            "initial_price_yes": price,
            "rationale": rationale.strip(),
        })
        if len(out) >= cap:
            break
    return out


def _fallback_from_goal(goal: str) -> list[dict[str, Any]]:
    q = (goal or "Will the simulated outcome occur?").strip()[:_QUESTION_MAX_LEN]
    return [{"question": q, "initial_price_yes": 0.5, "rationale": ""}]


def derive_markets(goal: str, enriched_seed: str, tier: str) -> dict[str, Any]:
    """Derive markets for a sim.

    Returns: {"markets": [...], "source": "llm" | "fallback_goal"}
    Always returns at least one market. Never raises.
    """
    cap = TIER_MARKET_CAPS.get(tier, TIER_MARKET_CAPS["small"])
    raw = _call_llm(goal, enriched_seed, cap)
    parsed = _parse_raw(raw or "")
    if parsed is None:
        logger.warning("markets.derivation_failed: unparseable or empty LLM output")
        return {"markets": _fallback_from_goal(goal), "source": DERIVATION_SOURCE_FALLBACK}
    markets = _validate(parsed, cap)
    if not markets:
        logger.warning("markets.derivation_failed: zero valid markets after validation")
        return {"markets": _fallback_from_goal(goal), "source": DERIVATION_SOURCE_FALLBACK}
    return {"markets": markets, "source": DERIVATION_SOURCE_LLM}
