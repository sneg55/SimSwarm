"""LLM-backed agent persona extraction from simulation activity.

Companion to simswarm.relations: where `extract_relations` produces
typed edges, this module produces one 2–3 sentence persona per agent
to replace the one-line activity summary that `extract_profiles` emits
by default.

Callers invoke `extract_personas(...)` once all other extractors have
run (so the sample posts and sentiment arcs are available) and then
merge the returned dict into the `profiles.json` payload. On any
failure the caller is expected to fall back to the existing one-liner.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from simswarm.llm import LLMClient

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

_MAX_PERSONA_CHARS = 1000


class PersonaExtractionError(Exception):
    """Raised when the LLM response cannot be parsed into personas."""


async def extract_personas(
    profiles: list[dict],
    llm: LLMClient,
    *,
    goal: str = "",
) -> dict[str, str]:
    """Ask the LLM for a 2–3 sentence persona per agent.

    *profiles* is a list of dicts with at minimum:
      agent_id, name, posts, actions, rounds_active, platforms,
      sample_posts (list[str]), sentiment_arc (str).

    Returns a dict mapping agent_id -> persona_text. Agents missing
    from the response, or with non-string values, are dropped silently
    (caller falls back to the one-liner for them).

    Short-circuits with {} if *profiles* is empty.
    """
    if not profiles:
        return {}

    prompt = _jinja_env.get_template("extract_personas.j2").render(
        agents=profiles,
        goal=goal,
    ).strip()

    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,  # slightly warmer than relations — these are descriptive
    )

    raw = (response.content or "").strip()
    if not raw:
        raise PersonaExtractionError("LLM returned empty response")

    data = _parse_json_object(raw)
    if not isinstance(data, dict):
        raise PersonaExtractionError(
            f"Expected JSON object, got {type(data).__name__}"
        )

    result: dict[str, str] = {}
    valid_ids = {p["agent_id"] for p in profiles}
    for agent_id, persona in data.items():
        if agent_id not in valid_ids:
            continue
        if not isinstance(persona, str):
            continue
        cleaned = persona.strip()
        if not cleaned:
            continue
        result[agent_id] = cleaned[:_MAX_PERSONA_CHARS]

    logger.info("personas.extracted count=%d requested=%d",
                len(result), len(profiles))
    return result


def _parse_json_object(text: str):
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise PersonaExtractionError("No JSON object found in LLM response")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PersonaExtractionError(f"Invalid JSON: {exc}") from exc
