"""Heuristic belief state updates.

Ported from MiroShark's belief_state.py. No LLM calls —
pure math based on trust, social proof, novelty, and confidence resistance.
"""
from __future__ import annotations

import copy

from simswarm.types import BeliefState

EXPOSURE_CAP = 2000
DEFAULT_TRUST = 0.5
NOVELTY_NEW = 1.5
NOVELTY_REPEAT = 0.5
SOCIAL_PROOF_FLOOR = 0.3
SOCIAL_PROOF_PER_LIKE = 0.07
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
