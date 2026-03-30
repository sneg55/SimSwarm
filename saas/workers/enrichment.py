"""Seed text enrichment via xAI web + X search."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    summary: str
    citations: list[dict]  # [{url, title}, ...]


def enrich_seed(seed_text: str, goal: str) -> EnrichmentResult | None:
    """Call xAI Responses API with web_search + x_search to research the seed topic.

    Returns EnrichmentResult on success, None on failure or missing API key.
    """
    api_key = os.getenv("XAI_API_KEY", "")
    if not api_key:
        logger.debug("XAI_API_KEY not set — skipping enrichment")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

        prompt = (
            "You are a research assistant preparing background material for a social media simulation.\n\n"
            f"SIMULATION GOAL: {goal}\n\n"
            f"SEED MATERIAL:\n{seed_text[:5000]}\n\n"
            "Research this topic thoroughly. Provide:\n"
            "1. Background context and key facts\n"
            "2. Key entities involved (people, organizations, policies) and their roles\n"
            "3. Recent developments and timeline\n"
            "4. Relevant social media discourse and public sentiment\n"
            "5. Any controversies or opposing viewpoints\n\n"
            "Be factual and cite your sources. Write 300-500 words."
        )

        response = client.responses.create(
            model="grok-3-mini",
            tools=[{"type": "web_search"}, {"type": "x_search"}],
            input=prompt,
            timeout=30,
        )

        summary = response.output_text or ""
        if not summary.strip():
            logger.warning("enrichment returned empty summary")
            return None

        citations = []
        for c in getattr(response, "citations", []) or []:
            url = getattr(c, "url", None) or (c.get("url") if isinstance(c, dict) else None)
            title = getattr(c, "title", None) or (c.get("title", "") if isinstance(c, dict) else "")
            if url:
                citations.append({"url": url, "title": title or ""})

        logger.info("enrichment.success goal=%s summary_len=%d citations=%d", goal[:50], len(summary), len(citations))
        return EnrichmentResult(summary=summary, citations=citations)

    except ImportError:
        logger.error("enrichment.failed openai package not installed — enrichment disabled")
        return None
    except Exception as exc:
        logger.warning("enrichment.failed error=%s", exc)
        return None
