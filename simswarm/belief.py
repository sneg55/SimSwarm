"""Belief dynamics for SimSwarm agents.

Pure, synchronous numerical model of how an agent's stance on a topic shifts
as it is exposed to peer content. No LLM calls, no async, no I/O.

Each exposure nudges the agent's position toward the post's stance, scaled by
how much the agent trusts the author, how much social validation the post has,
whether the content is novel, and how entrenched (confident) the agent already
is. Authors who echo the agent's resulting position earn trust; opponents lose
it. The agent's own engagement (likes/dislikes on its posts) feeds confidence.
"""
from __future__ import annotations

import copy

from simswarm.types import BeliefState

# How many distinct content hashes an agent remembers before old ones fall out.
EXPOSURE_CAP = 2000
# Trust assigned to an author the agent has never encountered.
DEFAULT_TRUST = 0.5
# Novelty multipliers: first-time content lands harder than rehashed content.
NOVELTY_NEW = 1.5
NOVELTY_REPEAT = 0.5
# Social-proof baseline so even zero-engagement posts carry weight, plus the
# per-like increment on top of that floor.
SOCIAL_PROOF_FLOOR = 0.3
SOCIAL_PROOF_PER_LIKE = 0.07
# Confidence response to the agent's own post reception.
CONFIDENCE_BOOST_PER_LIKE = 0.005
CONFIDENCE_DECAY_PER_DISLIKE = 0.008
# Step size for trust adjustments after each exposure.
TRUST_LEARNING_RATE = 0.05


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def update_beliefs(
    state: BeliefState,
    posts: list[dict],
    topic: str,
    own_likes: int = 0,
    own_dislikes: int = 0,
) -> BeliefState:
    """Return a NEW belief state reflecting one round of exposures.

    `state` is never mutated; every collection on the result is an independent
    copy. `posts` is an ordered list of dicts with keys ``author``,
    ``content_hash``, ``stance`` (in [-1, 1]) and ``likes``.
    """
    result = BeliefState(
        positions=copy.deepcopy(state.positions),
        confidence=copy.deepcopy(state.confidence),
        trust=copy.deepcopy(state.trust),
        exposure_history=set(state.exposure_history),
    )

    current_pos = state.positions.get(topic, 0.0)
    current_conf = state.confidence.get(topic, 0.5)
    # More confident agents resist change: the divisor grows with confidence.
    resistance = 0.3 + current_conf * 0.7

    position_delta = 0.0
    for post in posts:
        content_hash = post["content_hash"]
        seen = content_hash in result.exposure_history
        novelty = NOVELTY_REPEAT if seen else NOVELTY_NEW
        result.exposure_history.add(content_hash)

        trust = result.trust.get(post["author"], DEFAULT_TRUST)
        social_proof = SOCIAL_PROOF_FLOOR + post["likes"] * SOCIAL_PROOF_PER_LIKE
        influence = trust * social_proof * novelty / resistance

        gap = post["stance"] - current_pos
        position_delta += gap * influence * 0.1

    new_pos = _clamp(current_pos + position_delta, -1.0, 1.0)
    result.positions[topic] = new_pos

    # Trust evolution: authors aligned with the settled position gain trust,
    # opponents lose it. Unknown authors are seeded at DEFAULT_TRUST first.
    for post in posts:
        author = post["author"]
        alignment = 1.0 - abs(post["stance"] - new_pos) / 2.0
        trust_delta = (alignment - 0.5) * TRUST_LEARNING_RATE
        base = result.trust.get(author, DEFAULT_TRUST)
        result.trust[author] = _clamp(base + trust_delta, 0.0, 1.0)

    # Confidence reacts to the agent's own engagement; dislikes erode faster
    # than likes build. Runs even with no posts this round.
    conf_delta = (
        own_likes * CONFIDENCE_BOOST_PER_LIKE
        - own_dislikes * CONFIDENCE_DECAY_PER_DISLIKE
    )
    result.confidence[topic] = _clamp(current_conf + conf_delta, 0.0, 1.0)

    # Bound the memory footprint, dropping the oldest hashes first.
    if len(result.exposure_history) > EXPOSURE_CAP:
        ordered = list(result.exposure_history)
        keep = ordered[len(ordered) - EXPOSURE_CAP:]
        result.exposure_history = set(keep)

    return result


# Action types that count as authored content for belief exposure.
_POST_ACTIONS = {"create_post", "post", "comment", "reply"}


def apply_belief_updates(
    agents: dict,
    round_records: list,
    topic: str,
    likes_lookup: dict | None = None,
) -> None:
    """Apply one round of belief updates in place across all agents.

    Builds the set of posts authored this round, then for each agent recomputes
    its belief state from the posts authored by *others* (no self-influence),
    folding in the agent's own post reception as confidence signal.
    """
    likes_lookup = likes_lookup or {}

    authored = []
    for record in round_records:
        if not record.success:
            continue
        if record.action_type.lower() not in _POST_ACTIONS:
            continue

        args = record.action_args or {}
        text = args.get("text") or args.get("content")
        if not text:
            continue

        from simswarm.stance import score_stance

        stance = score_stance(text)
        content_hash = (
            f"r{record.round_num}:{record.agent_id}:"
            f"{hash(text) & 0xFFFFFFFF:08x}"
        )

        result = record.action_result
        post_id = result.get("post_id") if isinstance(result, dict) else None
        likes, dislikes = likes_lookup.get(post_id, (0, 0))

        authored.append({
            "author": record.agent_name,
            "agent_id": record.agent_id,
            "content_hash": content_hash,
            "stance": stance,
            "likes": likes,
            "dislikes": dislikes,
        })

    for agent in agents.values():
        exposures = [
            {
                "author": p["author"],
                "content_hash": p["content_hash"],
                "stance": p["stance"],
                "likes": p["likes"],
            }
            for p in authored
            if p["agent_id"] != agent.id
        ]
        own = [p for p in authored if p["agent_id"] == agent.id]
        own_likes = sum(p["likes"] for p in own)
        own_dislikes = sum(p["dislikes"] for p in own)

        if not exposures and own_likes == 0 and own_dislikes == 0:
            continue

        agent.belief_state = update_beliefs(
            agent.belief_state,
            posts=exposures,
            topic=topic,
            own_likes=own_likes,
            own_dislikes=own_dislikes,
        )
