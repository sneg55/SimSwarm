"""LLM-backed enrichment passes for the GPU worker job runner.

Provides:
  - enrich_profiles_with_personas()  — async: stamps LLM persona strings onto
    per-agent profile dicts extracted from the chat log.
"""
from __future__ import annotations

from simswarm.extractor import extract_agent_trajectories
from simswarm.extractor_common import is_post, post_text
from simswarm.llm import LLMClient
from simswarm.personas import PersonaExtractionError, extract_personas

# Threshold below which per-round sentiment endpoints are considered flat.
# score_sentiment returns (pos - neg) / total_words clamped to [-1, 1], so
# 0.15 roughly means "15 percent polarity shift across an agent's span."
_SENTIMENT_ARC_EPSILON = 0.15


async def enrich_profiles_with_personas(
    profiles: list[dict],
    chat_log: list,
    llm: LLMClient,
    *,
    goal: str = "",
    max_sample_posts: int = 5,
) -> list[dict]:
    """Mutate *profiles* in place with LLM-generated personas.

    On any failure (extraction error, unexpected exception, partial
    response, or setup error before the LLM call) the original one-liner
    persona is preserved for the affected agent. Returns the same list
    for caller convenience.
    """
    if not profiles or not chat_log:
        return profiles

    try:
        # Build sample posts per agent: up to *max_sample_posts*, taken in
        # chat-log order (early rounds will be over-represented for heavy
        # early posters — acceptable coarse sampling).
        samples: dict[str, list[str]] = {}
        for record in chat_log:
            if not is_post(record.action_type):
                continue
            text = post_text(record.action_args)
            if not text:
                continue
            lst = samples.setdefault(record.agent_id, [])
            if len(lst) < max_sample_posts:
                lst.append(text[:400])

        # Build a coarse sentiment-arc label from trajectories.
        arc_by_agent: dict[str, str] = {}
        for traj in extract_agent_trajectories(chat_log):
            rounds = traj.get("rounds") or []
            if not rounds:
                continue
            scores = [float(r.get("sentiment", 0.0)) for r in rounds]
            first, last = scores[0], scores[-1]
            if abs(last - first) < _SENTIMENT_ARC_EPSILON:
                arc = f"roughly steady around {sum(scores) / len(scores):+.2f}"
            elif last > first:
                arc = f"moves from {first:+.2f} to {last:+.2f} (upward)"
            else:
                arc = f"moves from {first:+.2f} to {last:+.2f} (downward)"
            arc_by_agent[traj["agent_id"]] = arc

        payload = [
            {
                "agent_id": p["agent_id"],
                "name": p["name"],
                "posts": p.get("total_posts", 0),
                "actions": p.get("total_actions", 0),
                "rounds_active": p.get("rounds_active", 0),
                "platforms": p.get("platforms", []),
                "sample_posts": samples.get(p["agent_id"], []),
                "sentiment_arc": arc_by_agent.get(p["agent_id"], "no activity recorded"),
            }
            for p in profiles
        ]

        personas = await extract_personas(payload, llm, goal=goal)
    except PersonaExtractionError as exc:
        print(f"personas.extraction_failed: {exc}", flush=True)
        return profiles
    except Exception as exc:
        print(f"personas.unexpected_error: {exc!r}", flush=True)
        return profiles

    for p in profiles:
        persona = personas.get(p["agent_id"])
        if persona:
            p["persona"] = persona
    return profiles
