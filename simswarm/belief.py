"""Heuristic belief state updates.

Ported from MiroShark's belief_state.py. No LLM calls —
pure math based on trust, social proof, novelty, and confidence resistance.
"""
from __future__ import annotations

import copy
import math

from simswarm.types import BeliefState

EXPOSURE_CAP = 2000
DEFAULT_TRUST = 0.5
NOVELTY_MULTIPLIER = 1.5
SOCIAL_PROOF_SCALE = 0.1  # log(1 + likes) * scale
CONFIDENCE_BOOST_PER_LIKE = 0.005
CONFIDENCE_DECAY_PER_DISLIKE = 0.008


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

    # Resistance factor: high confidence = resist change
    resistance = 1.0 - (current_conf * 0.8)  # range: 0.2 to 1.0

    position_delta = 0.0

    for post in posts:
        content_hash = post["content_hash"]

        # Skip already-seen content
        if content_hash in updated.exposure_history:
            continue

        # Mark as seen
        updated.exposure_history.add(content_hash)

        author = post["author"]
        stance = post["stance"]
        likes = post.get("likes", 0)

        # Trust weighting (default 0.5 for unknown authors)
        trust = updated.trust.get(author, DEFAULT_TRUST)

        # Social proof: log scale
        social_proof = math.log1p(likes) * SOCIAL_PROOF_SCALE

        # Novelty: new content has more impact
        novelty = NOVELTY_MULTIPLIER

        # Influence = trust * (1 + social_proof) * novelty * resistance
        influence = trust * (1.0 + social_proof) * novelty * resistance

        # Delta = stance * influence * 0.1 (scaled to keep updates small)
        position_delta += stance * influence * 0.1

    # Apply position update
    new_pos = current_pos + position_delta
    updated.positions[topic] = max(-1.0, min(1.0, new_pos))

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
