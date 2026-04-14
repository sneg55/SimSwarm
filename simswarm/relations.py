"""LLM-backed typed relation extraction from simulation post content.

Companion to simswarm.entities: where `extract_entities` identifies the
participants, this module identifies the semantic edges between them by
re-reading a sample of the simulation transcript. The output flows into
``build_graph(..., relations=...)`` and becomes the typed edges
(DISAGREES_WITH, SUPPORTS, RESPONDS_TO, ...) the frontend Graph tab used
to get from the pre-cutover Graphiti pipeline.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from simswarm.extractor_common import post_text
from simswarm.llm import LLMClient
from simswarm.types import ActionRecord, Entity

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)


class RelationExtractionError(Exception):
    """Raised when the LLM response cannot be parsed into relations."""


async def extract_relations(
    entities: list[Entity],
    chat_log: list[ActionRecord],
    llm: LLMClient,
    *,
    goal: str = "",
    max_posts: int = 60,
    max_relations: int = 30,
) -> list[dict]:
    """Ask the LLM for typed semantic edges between the given entities.

    Returns a list of dicts with keys ``source``, ``target``, ``type``,
    ``fact`` — source/target are the entity *names* (callers map to ids).
    Filters out self-loops and edges whose endpoints aren't in *entities*.
    Short-circuits with an empty list if there are no posts or no entities.
    """
    posts = _sample_posts(chat_log, max_posts)
    if not entities or not posts:
        return []

    prompt = _jinja_env.get_template("extract_relations.j2").render(
        entities=entities,
        posts=posts,
        goal=goal,
        max_relations=max_relations,
    ).strip()

    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,  # deterministic-ish: we want consistent extraction
    )

    raw = (response.content or "").strip()
    if not raw:
        raise RelationExtractionError("LLM returned empty response")

    data = _parse_json_array(raw)
    if not isinstance(data, list):
        raise RelationExtractionError(
            f"Expected JSON array, got {type(data).__name__}"
        )

    valid_names = {e.name for e in entities}
    result: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("relations.skip_non_dict index=%d", i)
            continue
        src = str(item.get("source", "")).strip()
        tgt = str(item.get("target", "")).strip()
        rtype = str(item.get("type", "")).strip().upper()
        fact = str(item.get("fact", "")).strip()
        if not src or not tgt or not rtype:
            continue
        if src == tgt:
            continue
        if src not in valid_names or tgt not in valid_names:
            continue
        result.append({
            "source": src,
            "target": tgt,
            "type": rtype[:40],
            "fact": fact[:400],
        })

    logger.info(
        "relations.extracted count=%d types=%s",
        len(result), sorted({r["type"] for r in result}),
    )
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _sample_posts(chat_log: list[ActionRecord], max_posts: int) -> list[dict]:
    """Return up to *max_posts* create_post records as {agent_id, content}."""
    out: list[dict] = []
    for r in chat_log:
        if r.action_type.lower() != "create_post":
            continue
        content = post_text(r.action_args)
        if not content:
            continue
        out.append({"agent_id": r.agent_id, "content": content})
        if len(out) >= max_posts:
            break
    return out


def _parse_json_array(text: str):
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise RelationExtractionError("No JSON array found in LLM response")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RelationExtractionError(f"Invalid JSON: {exc}") from exc
