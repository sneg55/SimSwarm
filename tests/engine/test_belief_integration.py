"""Engine-level tests proving belief_state actually mutates across rounds."""
from __future__ import annotations

from simswarm.belief import apply_belief_updates as _apply_belief_updates
from simswarm.stance import score_stance
from simswarm.types import (
    Agent,
    AgentActivityConfig,
    ActionRecord,
    BeliefState,
)


def _agent(id: str, name: str) -> Agent:
    return Agent(
        id=id,
        name=name,
        persona=name,
        environments=["social"],
        belief_state=BeliefState(),
        config=AgentActivityConfig(),
    )


def _record(agent_id: str, agent_name: str, text: str) -> ActionRecord:
    return ActionRecord(
        round_num=1,
        agent_id=agent_id,
        agent_name=agent_name,
        action_type="create_post",
        platform="social",
        action_args={"text": text},
        success=True,
    )


def test_score_stance_positive():
    assert score_stance("I fully support and endorse the proposal.") > 0


def test_score_stance_negative():
    assert score_stance("This is a dangerous and reckless idea we must oppose.") < 0


def test_score_stance_near_neutral_for_mild_text():
    # VADER scores "fine" as mildly positive (~0.2) — well within the
    # "near-neutral" band; the previous keyword scorer returned exactly 0.0.
    assert abs(score_stance("The weather is fine today.")) < 0.4


def test_apply_belief_updates_moves_position_toward_exposed_stance():
    """An agent exposed only to positive-stance posts from others should see
    positions[topic] drift positive."""
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}

    records = [
        _record("bob", "Bob", "I strongly support this peaceful reform."),
    ]
    _apply_belief_updates(agents, records, "reform")

    # Bob exposed no one else, so his state shouldn't have a reform entry.
    # Alice was exposed to Bob's positive post → reform position should be > 0.
    assert alice.belief_state.positions.get("reform", 0.0) > 0.0


def test_apply_belief_updates_negative_exposure_drifts_negative():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}

    records = [
        _record("bob", "Bob", "This is a dangerous corrupt attack we must reject."),
    ]
    _apply_belief_updates(agents, records, "topic")
    assert alice.belief_state.positions.get("topic", 0.0) < 0.0


def test_agents_dont_influence_themselves():
    alice = _agent("alice", "Alice")
    agents = {"alice": alice}
    records = [_record("alice", "Alice", "I endorse and support.")]
    _apply_belief_updates(agents, records, "t")
    # No other agents to expose Alice to; her state stays empty
    assert alice.belief_state.positions == {}


def test_non_post_actions_are_ignored():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}
    records = [
        ActionRecord(
            round_num=1, agent_id="bob", agent_name="Bob",
            action_type="browse_markets", platform="market",
            action_args={}, success=True,
        ),
    ]
    _apply_belief_updates(agents, records, "t")
    assert alice.belief_state.positions == {}


def test_empty_text_posts_dont_trigger_updates():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}
    records = [_record("bob", "Bob", "")]
    _apply_belief_updates(agents, records, "t")
    assert alice.belief_state.positions == {}


def test_apply_belief_updates_uses_post_likes_when_available():
    """Belief updates should pull likes from action_result.post_id, not assume 0."""
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}

    rec_no_likes = _record("bob", "Bob", "I support the peaceful reform.")
    rec_no_likes.action_result = {"post_id": "p1"}
    rec_with_likes = _record("bob", "Bob", "I support the peaceful reform.")
    rec_with_likes.action_result = {"post_id": "p2"}

    likes_lookup = {"p1": (0, 0), "p2": (10, 0)}

    from simswarm.belief import apply_belief_updates as _apply_belief_updates
    _apply_belief_updates(agents, [rec_no_likes], "t", likes_lookup=likes_lookup)
    after_low = alice.belief_state.positions.get("t", 0.0)

    alice2 = _agent("alice", "Alice")
    agents2 = {"alice": alice2, "bob": _agent("bob", "Bob")}
    _apply_belief_updates(agents2, [rec_with_likes], "t", likes_lookup=likes_lookup)
    after_high = alice2.belief_state.positions.get("t", 0.0)

    assert after_high > after_low


def test_own_post_likes_raise_confidence():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    alice.belief_state.confidence["topic"] = 0.5
    agents = {"alice": alice, "bob": bob}

    alice_rec = _record("alice", "Alice", "Neutral statement here.")
    alice_rec.action_result = {"post_id": "alice_post"}
    bob_rec = _record("bob", "Bob", "Some support text.")
    bob_rec.action_result = {"post_id": "bob_post"}

    likes_lookup = {"alice_post": (5, 0), "bob_post": (0, 0)}
    from simswarm.belief import apply_belief_updates as _apply_belief_updates
    _apply_belief_updates(agents, [alice_rec, bob_rec], "topic",
                          likes_lookup=likes_lookup)
    assert alice.belief_state.confidence["topic"] > 0.5


def test_own_post_dislikes_lower_confidence():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    alice.belief_state.confidence["topic"] = 0.5
    agents = {"alice": alice, "bob": bob}

    alice_rec = _record("alice", "Alice", "Neutral statement.")
    alice_rec.action_result = {"post_id": "alice_post"}
    bob_rec = _record("bob", "Bob", "Some support text.")
    bob_rec.action_result = {"post_id": "bob_post"}

    likes_lookup = {"alice_post": (0, 5), "bob_post": (0, 0)}
    from simswarm.belief import apply_belief_updates as _apply_belief_updates
    _apply_belief_updates(agents, [alice_rec, bob_rec], "topic",
                          likes_lookup=likes_lookup)
    assert alice.belief_state.confidence["topic"] < 0.5


def test_repeated_exposure_still_nudges_at_lower_weight():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}

    post_text = "I firmly support the peaceful reform."
    records = [_record("bob", "Bob", post_text)]

    _apply_belief_updates(agents, records, "t")
    after_first = alice.belief_state.positions.get("t", 0.0)
    assert after_first > 0.0

    # Same content_hash -> in exposure_history -> 0.5x novelty,
    # so position keeps moving but slower.
    _apply_belief_updates(agents, records, "t")
    after_second = alice.belief_state.positions.get("t", 0.0)
    delta_first = after_first
    delta_second = after_second - after_first
    assert delta_second > 0.0  # still moves
    assert delta_second < delta_first  # but less than the novel exposure
