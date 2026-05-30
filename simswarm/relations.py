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

    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
    data, raw = await _call_and_parse(llm, messages)
    if not isinstance(data, list):
        raise RelationExtractionError(
            f"Expected JSON array, got {type(data).__name__}"
        )

    canonical = _build_canonical_name_lookup(entities)
    result: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("relations.skip_non_dict index=%d", i)
            continue
        raw_src = str(item.get("source", "")).strip()
        raw_tgt = str(item.get("target", "")).strip()
        rtype = str(item.get("type", "")).strip().upper()
        fact = str(item.get("fact", "")).strip()
        if not raw_src or not raw_tgt or not rtype:
            continue
        src = canonical.get(raw_src) or canonical.get(raw_src.lower())
        tgt = canonical.get(raw_tgt) or canonical.get(raw_tgt.lower())
        if not src or not tgt or src == tgt:
            continue
        result.append({
            "source": src,
            "target": tgt,
            "type": rtype[:40],
            "fact": fact[:400],
        })

    if not result and data:
        # Every row was filtered. Surface the raw response preview so a
        # silent zero-edge regression (see prod sim #112) is diagnosable
        # from celery logs without re-running the pipeline.
        logger.warning(
            "relations.empty_after_filter raw_response=%s",
            raw[:500],
        )
    logger.info(
        "relations.extracted count=%d types=%s",
        len(result), sorted({r["type"] for r in result}),
    )
    return result


def _build_canonical_name_lookup(entities: list[Entity]) -> dict[str, str]:
    """Map any plausible name/id variant the LLM might emit back to
    ``entity.name``. Covers: canonical name, lowered name, entity.id,
    lowered entity.id. Earlier entries win on collision."""
    lookup: dict[str, str] = {}
    for e in entities:
        for key in (e.name, e.name.lower(), e.id, e.id.lower()):
            if key and key not in lookup:
                lookup[key] = e.name
    return lookup


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _sample_posts(chat_log: list[ActionRecord], max_posts: int) -> list[dict]:
    """Return up to *max_posts* create_post records as {author, content}.

    ``author`` is the agent's display name (falling back to agent_id) so the
    prompt shows the LLM one consistent naming style — the same one that
    appears in the entity list. Previously we showed snake_case agent_ids
    here, which biased the LLM into echoing those ids back as source/target
    values and caused every relation to be dropped by name filtering (prod
    sim #112 regression)."""
    out: list[dict] = []
    for r in chat_log:
        if r.action_type.lower() != "create_post":
            continue
        content = post_text(r.action_args)
        if not content:
            continue
        author = r.agent_name or r.agent_id
        out.append({"author": author, "content": content})
        if len(out) >= max_posts:
            break
    return out


async def _call_and_parse(llm: LLMClient, messages: list[dict[str, str]]):
    """One LLM call + parse, with a single repair retry on parse failure.

    On the first failure we log a preview of the raw response (previously
    swallowed — see sim #128, where the failure mode was diagnosable only
    by re-running the pipeline) and append a stricter repair instruction
    before retrying."""
    response = await llm.chat(messages=messages, temperature=0.2)
    raw = (response.content or "").strip()
    if not raw:
        raise RelationExtractionError("LLM returned empty response")
    try:
        return _parse_json_array(raw), raw
    except RelationExtractionError as exc:
        logger.warning(
            "relations.parse_failed error=%s raw_preview=%r",
            exc, raw[:500],
        )
        repair_messages = list(messages) + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content":
                "Your previous response could not be parsed as JSON. "
                "Reply with ONLY a JSON array of relation objects and no "
                "other text. If there are no substantive relations, reply "
                "with the empty array []."},
        ]
        retry = await llm.chat(messages=repair_messages, temperature=0.0)
        raw_retry = (retry.content or "").strip()
        if not raw_retry:
            raise RelationExtractionError(
                f"LLM returned empty response on retry (first: {exc})"
            ) from exc
        try:
            return _parse_json_array(raw_retry), raw_retry
        except RelationExtractionError as exc2:
            logger.warning(
                "relations.parse_failed_retry error=%s raw_preview=%r",
                exc2, raw_retry[:500],
            )
            raise


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
