"""Regression tests: post extractors must read action_args["text"] OR
action_args["content"].

The native social environment stores post bodies under the `text` key
(see simswarm/environments/social.py:127) but every extractor was only
reading `content`. Result on prod job 107: every extracted post had
content="", which starved relation extraction (→ 0 edges) and rendered
empty Top Posts cards in the Data tab.
"""
from __future__ import annotations

import pytest

from simswarm.extractor import extract_posts, extract_top_posts
from simswarm.extractor_activity import extract_agent_trajectories
from simswarm.relations import extract_relations
from simswarm.llm import LLMResponse
from simswarm.types import ActionRecord, Entity


def _post_with_text(agent_id: str, agent_name: str, text: str) -> ActionRecord:
    """A post record shaped like what the real sim produces."""
    return ActionRecord(
        round_num=1, agent_id=agent_id, agent_name=agent_name,
        action_type="create_post", platform="social",
        action_args={"text": text},  # note: "text", not "content"
        timestamp="t", success=True,
    )


class _StubLLM:
    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, temperature=0.7):
        self.calls.append({"messages": messages, "temperature": temperature})
        return LLMResponse(content=self._content, tool_calls=[], raw={})

    async def close(self):
        pass


def test_extract_posts_reads_text_key():
    record = _post_with_text("alice", "Alice", "Hello world")
    posts = extract_posts([record])
    assert posts[0]["content"] == "Hello world"


def test_extract_posts_still_reads_content_key():
    """Backward-compat: older records with `content` must still work."""
    record = ActionRecord(
        round_num=1, agent_id="alice", agent_name="Alice",
        action_type="create_post", platform="social",
        action_args={"content": "Hello world"},
        timestamp="t", success=True,
    )
    posts = extract_posts([record])
    assert posts[0]["content"] == "Hello world"


def test_extract_top_posts_reads_text_key():
    record = _post_with_text("alice", "Alice", "Top post text")
    top = extract_top_posts([record])
    assert top[0]["content"] == "Top post text"


def test_extract_agent_trajectories_scores_text_key():
    """Sentiment scoring must see the actual post body via `text` key."""
    records = [
        _post_with_text("alice", "Alice", "great success wonderful progress"),
    ]
    result = extract_agent_trajectories(records)
    # Alice's round should have non-zero positive sentiment
    alice_round = result[0]["rounds"][0]
    assert alice_round["sentiment"] > 0.0


@pytest.mark.asyncio
async def test_extract_relations_sees_text_key_posts():
    """Without this fix, _sample_posts drops every post ⇒ empty list ⇒
    extract_relations short-circuits before calling the LLM."""
    llm = _StubLLM(
        '[{"source":"Alice","target":"Bob","type":"DISAGREES_WITH","fact":"f"}]'
    )
    entities = [
        Entity(id="alice", name="Alice", type="person", summary=""),
        Entity(id="bob", name="Bob", type="person", summary=""),
    ]
    log = [
        _post_with_text("alice", "Alice", "I disagree with Bob's plan."),
        _post_with_text("bob", "Bob", "Alice's reading is incomplete."),
    ]
    rels = await extract_relations(entities, log, llm)
    # The LLM must have been called (proves posts were not all filtered out).
    assert len(llm.calls) == 1
    # The prompt body must contain the real post text.
    prompt = llm.calls[0]["messages"][0]["content"]
    assert "disagree" in prompt.lower()
    assert len(rels) == 1
