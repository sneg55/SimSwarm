"""Test belief state updates with known inputs and expected outputs.

These are pure math tests — no LLM, no environment, no async.
"""
from __future__ import annotations

from simswarm.belief import update_beliefs
from simswarm.types import BeliefState


class TestPositionUpdate:
    def test_novel_supportive_content_shifts_position_positive(self):
        bs = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": 0.6, "likes": 3}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] > 0.0

    def test_novel_opposing_content_shifts_position_negative(self):
        bs = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h2", "stance": -0.6, "likes": 3}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] < 0.0

    def test_repeated_content_has_half_effect(self):
        """Re-seen posts still nudge at 0.5x (MiroShark bidirectional novelty)."""
        bs_first = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        bs_repeat = BeliefState(
            positions={"climate": 0.0},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
            exposure_history={"h1"},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": 0.6, "likes": 0}]
        first = update_beliefs(bs_first, posts, topic="climate")
        repeat = update_beliefs(bs_repeat, posts, topic="climate")

        assert first.positions["climate"] > 0.0
        assert repeat.positions["climate"] > 0.0
        # Repeat is roughly half the magnitude of novel (0.5 / 1.5 = 1/3).
        assert repeat.positions["climate"] < first.positions["climate"]

    def test_agent_at_post_stance_does_not_drift(self):
        """Pull formulation: when current_pos == post_stance, delta is zero."""
        bs = BeliefState(
            positions={"climate": 0.6},
            confidence={"climate": 0.5},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": 0.6, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert abs(updated.positions["climate"] - 0.6) < 1e-9

    def test_agent_past_post_stance_pulled_back(self):
        """Pull formulation: agent at +0.9 exposed to +0.5 post drifts negative."""
        bs = BeliefState(
            positions={"climate": 0.9},
            confidence={"climate": 0.3},
            trust={"author1": 0.8},
        )
        posts = [{"author": "author1", "content_hash": "h1", "stance": 0.5, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="climate")
        assert updated.positions["climate"] < 0.9
        assert updated.positions["climate"] > 0.5


class TestSocialProof:
    def test_zero_likes_post_still_has_baseline_social_proof(self):
        """Floor at 0.3: zero-engagement posts still nudge non-trivially."""
        bs = BeliefState(
            positions={"t": 0.0}, confidence={"t": 0.0}, trust={"a": 1.0},
        )
        posts = [{"author": "a", "content_hash": "h", "stance": 1.0, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="t")
        # With trust=1, novelty=1.5, resistance via divisor=0.3,
        # social_proof=0.3, gap=1.0, the delta should be substantial (> 0.04).
        assert updated.positions["t"] > 0.04

    def test_likes_increase_influence_linearly(self):
        """Linear social proof: more likes = more influence."""
        bs_low = BeliefState(positions={"t": 0.0}, confidence={"t": 0.0}, trust={"a": 0.5})
        bs_high = BeliefState(positions={"t": 0.0}, confidence={"t": 0.0}, trust={"a": 0.5})
        posts_low = [{"author": "a", "content_hash": "h1", "stance": 1.0, "likes": 1}]
        posts_high = [{"author": "a", "content_hash": "h2", "stance": 1.0, "likes": 20}]
        u_low = update_beliefs(bs_low, posts_low, topic="t")
        u_high = update_beliefs(bs_high, posts_high, topic="t")
        assert u_high.positions["t"] > u_low.positions["t"]


class TestConfidenceResistance:
    def test_high_confidence_resists_change(self):
        low_conf = BeliefState(
            positions={"topic": 0.0}, confidence={"topic": 0.2}, trust={"a": 0.8},
        )
        high_conf = BeliefState(
            positions={"topic": 0.0}, confidence={"topic": 0.9}, trust={"a": 0.8},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": 0.8, "likes": 5}]
        updated_low = update_beliefs(low_conf, posts, topic="topic")
        updated_high = update_beliefs(high_conf, posts, topic="topic")
        assert abs(updated_low.positions["topic"]) > abs(updated_high.positions["topic"])

    def test_full_confidence_almost_fully_resists(self):
        """Confidence=1.0 -> resistance divisor ~1.0; confidence=0.0 -> divisor ~0.3.
        High-confidence agent moves much less than low-confidence one."""
        low = BeliefState(positions={"t": 0.0}, confidence={"t": 0.0}, trust={"a": 0.8})
        high = BeliefState(positions={"t": 0.0}, confidence={"t": 1.0}, trust={"a": 0.8})
        posts = [{"author": "a", "content_hash": "h", "stance": 1.0, "likes": 5}]
        u_low = update_beliefs(low, posts, topic="t")
        u_high = update_beliefs(high, posts, topic="t")
        # low gets divided by 0.3, high gets divided by 1.0 -> low moves ~3.3x more.
        assert u_low.positions["t"] > 2.5 * u_high.positions["t"]

    def test_confidence_increases_with_engagement(self):
        bs = BeliefState(
            positions={"topic": 0.5}, confidence={"topic": 0.5}, trust={},
        )
        updated = update_beliefs(bs, [], topic="topic", own_likes=10, own_dislikes=0)
        assert updated.confidence["topic"] > 0.5


class TestTrustUpdate:
    def test_trust_defaults_to_half_for_unknown_author(self):
        """Unknown author starts at 0.5 trust on first exposure (after update)."""
        bs = BeliefState()
        posts = [{"author": "stranger", "content_hash": "h1", "stance": 0.5, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="t")
        # First exposure: trust gets seeded then nudged. Should still be near 0.5.
        assert 0.3 < updated.trust["stranger"] < 0.7

    def test_aligned_author_gains_trust(self):
        """Author whose post matches the agent's resulting position gains trust."""
        bs = BeliefState(
            positions={"t": 0.5}, confidence={"t": 0.7},
            trust={"ally": 0.5},
        )
        posts = [{"author": "ally", "content_hash": "h", "stance": 0.5, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="t")
        assert updated.trust["ally"] > 0.5

    def test_opposing_author_loses_trust(self):
        """Author posting at opposite stance loses trust."""
        bs = BeliefState(
            positions={"t": 0.8}, confidence={"t": 0.9},  # high conf -> resists much
            trust={"opponent": 0.5},
        )
        posts = [{"author": "opponent", "content_hash": "h", "stance": -0.8, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="t")
        assert updated.trust["opponent"] < 0.5

    def test_trust_clamped_to_unit_interval(self):
        bs = BeliefState(
            positions={"t": 1.0}, confidence={"t": 1.0},
            trust={"a": 0.99},
        )
        posts = [{"author": "a", "content_hash": "h", "stance": 1.0, "likes": 0}]
        updated = update_beliefs(bs, posts, topic="t")
        assert 0.0 <= updated.trust["a"] <= 1.0


class TestExposureHistory:
    def test_new_content_added_to_history(self):
        bs = BeliefState()
        posts = [{"author": "a", "content_hash": "new_hash", "stance": 0.5, "likes": 1}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert "new_hash" in updated.exposure_history

    def test_history_capped_at_2000(self):
        bs = BeliefState(
            exposure_history={f"h{i}" for i in range(2000)},
        )
        posts = [{"author": "a", "content_hash": "overflow", "stance": 0.5, "likes": 1}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert len(updated.exposure_history) <= 2000


class TestPositionBounds:
    def test_position_clamped_to_negative_one(self):
        bs = BeliefState(
            positions={"topic": -0.95}, confidence={"topic": 0.1}, trust={"a": 1.0},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": -1.0, "likes": 100}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert updated.positions["topic"] >= -1.0

    def test_position_clamped_to_positive_one(self):
        bs = BeliefState(
            positions={"topic": 0.95}, confidence={"topic": 0.1}, trust={"a": 1.0},
        )
        posts = [{"author": "a", "content_hash": "h1", "stance": 1.0, "likes": 100}]
        updated = update_beliefs(bs, posts, topic="topic")
        assert updated.positions["topic"] <= 1.0
