"""Heuristic belief state updates.

Ported from MiroShark's belief_state.py. No LLM calls —
pure math based on trust, social proof, novelty, and confidence resistance.
"""
from __future__ import annotations

import copy
from typing import Any

from simswarm.stance import score_stance
from simswarm.types import ActionRecord, Agent, BeliefState

EXPOSURE_CAP = 2000
DEFAULT_TRUST = 0.5
NOVELTY_NEW = 1.5
NOVELTY_REPEAT = 0.5
SOCIAL_PROOF_FLOOR = 0.3
SOCIAL_PROOF_PER_LIKE = 0.07
CONFIDENCE_BOOST_PER_LIKE = 0.005
CONFIDENCE_DECAY_PER_DISLIKE = 0.008
TRUST_LEARNING_RATE = 0.05


def update_beliefs(
    state: BeliefState,
    posts: list[dict],
    topic: str,
    own_likes: int = 0,
    own_dislikes: int = 0,
) -> BeliefState:
    """Return a new BeliefState with updated positions, confidence, trust, and exposure.

    Args:
        state: Current belief state (not mutated).
        posts: List of dicts with keys: author, content_hash, stance (-1 to 1), likes.
        topic: The topic being updated.
        own_likes: Likes received on agent's own posts this round.
        own_dislikes: Dislikes received on agent's own posts this round.
    """
    updated = copy.deepcopy(state)

    current_pos = updated.positions.get(topic, 0.0)
    current_conf = updated.confidence.get(topic, 0.5)

    # Resistance divisor: high confidence = larger divisor = smaller nudge.
    resistance = 0.3 + current_conf * 0.7  # range: 0.3 to 1.0

    position_delta = 0.0

    for post in posts:
        content_hash = post["content_hash"]
        seen_before = content_hash in updated.exposure_history
        novelty = NOVELTY_REPEAT if seen_before else NOVELTY_NEW

        # Mark as seen (idempotent for repeats)
        updated.exposure_history.add(content_hash)

        author = post["author"]
        stance = post["stance"]
        likes = post.get("likes", 0)

        # Trust weighting (default 0.5 for unknown authors)
        trust = updated.trust.get(author, DEFAULT_TRUST)

        # Social proof: linear with floor (zero-engagement posts still register)
        social_proof = SOCIAL_PROOF_FLOOR + likes * SOCIAL_PROOF_PER_LIKE

        # Influence = trust * social_proof * novelty / resistance
        influence = trust * social_proof * novelty / resistance

        # Pull-toward-stance: nudge proportional to gap between post and current position.
        gap = stance - current_pos
        position_delta += gap * influence * 0.1

    # Apply position update
    new_pos = current_pos + position_delta
    updated.positions[topic] = max(-1.0, min(1.0, new_pos))

    # Trust evolution: authors whose stance matches the agent's resulting
    # position gain trust; those who oppose lose it.
    new_position = updated.positions[topic]
    for post in posts:
        author = post["author"]
        if author not in updated.trust:
            updated.trust[author] = DEFAULT_TRUST
        stance = post["stance"]
        # alignment in [0, 1]: 1 = same position, 0 = polar opposite
        alignment = 1.0 - abs(stance - new_position) / 2.0
        trust_delta = (alignment - 0.5) * TRUST_LEARNING_RATE
        updated.trust[author] = max(0.0, min(1.0, updated.trust[author] + trust_delta))

    # Confidence update from own engagement
    conf_delta = (own_likes * CONFIDENCE_BOOST_PER_LIKE
                  - own_dislikes * CONFIDENCE_DECAY_PER_DISLIKE)
    new_conf = current_conf + conf_delta
    updated.confidence[topic] = max(0.0, min(1.0, new_conf))

    # Cap exposure history
    if len(updated.exposure_history) > EXPOSURE_CAP:
        excess = len(updated.exposure_history) - EXPOSURE_CAP
        to_remove = list(updated.exposure_history)[:excess]
        for item in to_remove:
            updated.exposure_history.discard(item)

    return updated


# ---------------------------------------------------------------------------
# Engine integration: build the {post_id: (likes, dislikes)} payload from
# ActionRecords and apply update_beliefs to every exposed agent.
# ---------------------------------------------------------------------------


def apply_belief_updates(
    agents: dict[str, Agent],
    round_records: list[ActionRecord],
    topic: str,
    likes_lookup: dict[str, tuple[int, int]] | None = None,
) -> None:
    """Update each agent's belief state from the other agents' posts this round.

    Mutates Agent.belief_state in place. Own posts are skipped (agents don't
    influence themselves). Stance is scored from post text via
    simswarm.stance.score_stance. Engagement (likes/dislikes) is looked up
    by post_id via *likes_lookup* — typically built from each social
    environment's current_engagement() snapshot.
    """
    post_actions = [
        r for r in round_records
        if r.success
        and r.action_type.lower() in ("create_post", "post", "comment", "reply")
    ]

    posts_by_author: dict[str, list[dict[str, Any]]] = {}
    for action in post_actions:
        text = (action.action_args or {}).get("text") or \
            (action.action_args or {}).get("content") or ""
        if not text:
            continue
        stance = score_stance(text)
        content_hash = f"r{action.round_num}:{action.agent_id}:{hash(text) & 0xffffffff:08x}"
        post_id = (action.action_result or {}).get("post_id")
        if likes_lookup and post_id in likes_lookup:
            likes, dislikes = likes_lookup[post_id]
        else:
            likes, dislikes = 0, 0
        posts_by_author.setdefault(action.agent_id, []).append({
            "author": action.agent_name,
            "content_hash": content_hash,
            "stance": stance,
            "likes": likes,
            "dislikes": dislikes,
        })

    own_engagement: dict[str, tuple[int, int]] = {}
    for action in post_actions:
        post_id = (action.action_result or {}).get("post_id")
        if not post_id or not likes_lookup or post_id not in likes_lookup:
            continue
        l, d = likes_lookup[post_id]
        prev_l, prev_d = own_engagement.get(action.agent_id, (0, 0))
        own_engagement[action.agent_id] = (prev_l + l, prev_d + d)

    if not posts_by_author and not own_engagement:
        return

    for agent_id, agent in agents.items():
        exposures = [
            post for author_id, posts in posts_by_author.items()
            if author_id != agent_id
            for post in posts
        ]
        own_l, own_d = own_engagement.get(agent_id, (0, 0))
        if not exposures and own_l == 0 and own_d == 0:
            continue
        agent.belief_state = update_beliefs(
            state=agent.belief_state,
            posts=exposures,
            topic=topic,
            own_likes=own_l,
            own_dislikes=own_d,
        )
