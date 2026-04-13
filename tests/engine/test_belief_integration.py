"""Engine-level tests proving belief_state actually mutates across rounds."""
from __future__ import annotations

from simswarm.engine import _apply_belief_updates
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


def test_score_stance_neutral_when_no_keywords():
    assert score_stance("The weather is fine today.") == 0.0


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


def test_repeated_exposure_dedupes_via_content_hash_within_state():
    alice = _agent("alice", "Alice")
    bob = _agent("bob", "Bob")
    agents = {"alice": alice, "bob": bob}

    post_text = "I firmly support the peaceful reform."
    records = [_record("bob", "Bob", post_text)]

    _apply_belief_updates(agents, records, "t")
    after_first = alice.belief_state.positions.get("t", 0.0)
    assert after_first > 0.0

    # Same round-stamped post hash → should be in exposure_history → no further
    # position change.
    _apply_belief_updates(agents, records, "t")
    after_second = alice.belief_state.positions.get("t", 0.0)
    assert after_second == after_first
