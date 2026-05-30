"""Simswarm-native entity extraction.

A single LLM call asks
the smart model to list the most relevant entities for the simulation goal,
and we parse its JSON response into Entity dataclasses.

Kept in a dedicated module (rather than inside run_job_v2) so the engine
library can be used standalone with no infra/docker/ imports.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from simswarm.llm import LLMClient
from simswarm.types import Entity

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

# Short common words that the naive title-case fallback mis-identifies as
# entities. Cheap filter — the LLM path is the primary mechanism.
_STOP_WORDS: frozenset[str] = frozenset({
    "A", "An", "The", "I", "He", "She", "It", "We", "They",
    "This", "That", "These", "Those", "Some", "Any", "All",
    "As", "But", "Or", "And", "Is", "Was", "Be",
})


class EntityExtractionError(Exception):
    """Raised when the LLM response cannot be parsed into entities."""


async def extract_entities(
    seed_text: str,
    goal: str,
    count: int,
    llm: LLMClient,
) -> list[Entity]:
    """Ask the LLM for a JSON list of entities, parse into Entity objects.

    Raises EntityExtractionError if the response can't be parsed. Callers should
    fall back to `fallback_entities` on that exception.
    """
    prompt = _jinja_env.get_template("extract_entities.j2").render(
        seed_text=seed_text, goal=goal, count=count,
    ).strip()

    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,  # Lower temp — we want consistent extraction, not creativity
    )

    raw = (response.content or "").strip()
    if not raw:
        raise EntityExtractionError("LLM returned empty response")

    data = _parse_json_array(raw)
    if not isinstance(data, list):
        raise EntityExtractionError(f"Expected JSON array, got {type(data).__name__}")

    entities: list[Entity] = []
    for i, item in enumerate(data[:count]):
        if not isinstance(item, dict):
            logger.warning("entities.skip_non_dict index=%d", i)
            continue
        name = str(item.get("name", "")).strip()
        if not name or len(name) < 2:
            continue
        etype = str(item.get("type", "person")).strip() or "person"
        summary = str(item.get("summary", "")).strip()
        eid = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or f"entity_{i}"
        entities.append(Entity(
            id=eid,
            name=name[:80],
            type=etype,
            summary=summary or f"{name} is an entity identified in the seed document.",
        ))

    if not entities:
        raise EntityExtractionError("No usable entities parsed from LLM response")

    logger.info(
        "entities.extracted count=%d names=%s",
        len(entities), [e.name for e in entities],
    )
    return entities


def fallback_entities(seed_text: str, count: int) -> list[Entity]:
    """Capitalized-word extraction when the LLM path is unavailable.

    Filters out English articles and pronouns that the v1 naive version
    accepted. Returns at least one entity.
    """
    words = seed_text.split()
    seen: list[str] = []
    seen_lower: set[str] = set()
    for w in words:
        cleaned = w.strip(".,!?;:\"'()-[]")
        if not cleaned or len(cleaned) < 3:
            continue
        if cleaned in _STOP_WORDS:
            continue
        if cleaned[0].isupper() and cleaned.lower() not in seen_lower:
            seen_lower.add(cleaned.lower())
            seen.append(cleaned)

    selected = seen[:count] if seen else ["Entity"]
    return [
        Entity(
            id=re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or f"entity_{i}",
            name=name,
            type="person",
            summary=f"{name} is a key entity identified in the seed document.",
        )
        for i, name in enumerate(selected)
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_json_array(text: str):
    """Extract the first JSON array from *text*.

    Handles common model quirks: markdown code fences, leading prose,
    trailing commentary. Raises EntityExtractionError if no valid JSON
    array can be found.
    """
    # Strip fenced code blocks
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        # Find the first '[' and last ']' to slice the array
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise EntityExtractionError("No JSON array found in LLM response")
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise EntityExtractionError(f"Invalid JSON: {exc}") from exc
