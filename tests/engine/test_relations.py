"""Tests for simswarm.relations — LLM-backed typed relation extraction.

This is the post-cutover replacement for the Graphiti `RESPONDS_TO` /
`INFLUENCES` edges that the old MiroShark pipeline used to extract from
agent post content. Without it, the native graph only has follow/like/
mention interaction edges — typically zero edges for analytic topics
where agents mostly monologue.
"""
from __future__ import annotations

import pytest

from simswarm.llm import LLMResponse
from simswarm.relations import RelationExtractionError, extract_relations
from simswarm.types import ActionRecord, Entity


class _StubLLM:
    def __init__(self, content):
        # Accept a single string (same response every call) or a list of
        # strings (one per call, for testing the parse/retry path).
        if isinstance(content, list):
            self._responses = list(content)
        else:
            self._responses = [content]
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, temperature=0.7):
        self.calls.append({"messages": messages, "temperature": temperature})
        if len(self._responses) > 1:
            content = self._responses.pop(0)
        else:
            content = self._responses[0]
        return LLMResponse(content=content, tool_calls=[], raw={})

    async def close(self):
        pass


def _entity(name: str, etype: str = "person") -> Entity:
    return Entity(id=name.lower().replace(" ", "_"), name=name, type=etype, summary="")


def _post(agent_id: str, agent_name: str, content: str, round_num: int = 1) -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type="create_post", platform="twitter",
        action_args={"content": content}, timestamp="t", success=True,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_relations_happy_path():
    llm = _StubLLM(
        '[{"source": "Alice", "target": "Bob", "type": "DISAGREES_WITH", '
        '"fact": "Alice rejects Bobs framework as incomplete."}]'
    )
    ents = [_entity("Alice"), _entity("Bob")]
    log = [_post("alice", "Alice", "I disagree with Bob.")]
    rels = await extract_relations(ents, log, llm)
    assert len(rels) == 1
    assert rels[0]["source"] == "Alice"
    assert rels[0]["target"] == "Bob"
    assert rels[0]["type"] == "DISAGREES_WITH"
    assert "rejects" in rels[0]["fact"]


@pytest.mark.asyncio
async def test_extract_relations_empty_chat_log_returns_empty():
    llm = _StubLLM("[]")
    rels = await extract_relations([_entity("A")], [], llm)
    assert rels == []
    # Should short-circuit — no LLM call when there are no posts to analyse.
    assert llm.calls == []


@pytest.mark.asyncio
async def test_extract_relations_no_entities_returns_empty():
    llm = _StubLLM('[{"source":"x","target":"y","type":"T","fact":"f"}]')
    rels = await extract_relations([], [_post("a", "A", "hi")], llm)
    assert rels == []
    assert llm.calls == []


# ---------------------------------------------------------------------------
# Filtering / validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_relations_drops_unknown_entity_names():
    llm = _StubLLM(
        '[{"source": "Alice", "target": "Unknown Person", "type": "T", "fact": "f"},'
        ' {"source": "Alice", "target": "Bob", "type": "T", "fact": "f"}]'
    )
    rels = await extract_relations(
        [_entity("Alice"), _entity("Bob")],
        [_post("alice", "Alice", "x")],
        llm,
    )
    # Only the edge with both endpoints in the entity set survives.
    assert len(rels) == 1
    assert rels[0]["target"] == "Bob"


@pytest.mark.asyncio
async def test_extract_relations_drops_self_loops():
    llm = _StubLLM('[{"source":"Alice","target":"Alice","type":"T","fact":"f"}]')
    rels = await extract_relations(
        [_entity("Alice")],
        [_post("alice", "Alice", "x")],
        llm,
    )
    assert rels == []


@pytest.mark.asyncio
async def test_extract_relations_samples_posts_up_to_max():
    llm = _StubLLM("[]")
    ents = [_entity("Alice")]
    log = [_post("alice", "Alice", f"post {i}") for i in range(100)]
    await extract_relations(ents, log, llm, max_posts=10)
    # The prompt should include exactly 10 posts, attributed by entity name
    # (not agent_id) so the LLM uses canonical names in its response.
    prompt = llm.calls[0]["messages"][0]["content"]
    assert prompt.count("Alice:") == 10
    assert "alice:" not in prompt  # agent_id form should not leak into prompt


# ---------------------------------------------------------------------------
# Fuzzy name resolution — regression for sim #112 (relations.extracted
# count=0 on valid data because the LLM emitted snake_case ids instead of
# canonical names while the filter was strict case-sensitive match).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_relations_resolves_snake_case_ids_to_canonical_names():
    """LLM emits agent_id style (`jpmorgan`) instead of the canonical
    entity.name (`JPMorgan`); we should still keep the edge and return the
    canonical name so downstream id-lookups in _relations_to_edges work."""
    llm = _StubLLM(
        '[{"source": "jpmorgan", "target": "goldman_sachs", '
        '"type": "DISAGREES_WITH", "fact": "JPM and GS differ on scope."}]'
    )
    ents = [_entity("JPMorgan", "organization"), _entity("Goldman Sachs", "organization")]
    log = [_post("jpmorgan", "JPMorgan", "we disagree")]
    rels = await extract_relations(ents, log, llm)
    assert len(rels) == 1
    assert rels[0]["source"] == "JPMorgan"
    assert rels[0]["target"] == "Goldman Sachs"


@pytest.mark.asyncio
async def test_extract_relations_resolves_case_insensitive_names():
    llm = _StubLLM(
        '[{"source": "alice", "target": "BOB", "type": "T", "fact": "f"}]'
    )
    rels = await extract_relations(
        [_entity("Alice"), _entity("Bob")],
        [_post("alice", "Alice", "x")],
        llm,
    )
    assert len(rels) == 1
    assert rels[0]["source"] == "Alice"
    assert rels[0]["target"] == "Bob"


@pytest.mark.asyncio
async def test_extract_relations_logs_raw_response_when_empty_after_filter(caplog):
    """When every row is filtered out, log the raw LLM response so future
    silent-failure regressions are diagnosable from celery logs."""
    import logging
    llm = _StubLLM(
        '[{"source": "Unknown", "target": "Also Unknown", "type": "T", "fact": "f"}]'
    )
    with caplog.at_level(logging.WARNING, logger="simswarm.relations"):
        rels = await extract_relations(
            [_entity("Alice"), _entity("Bob")],
            [_post("alice", "Alice", "x")],
            llm,
        )
    assert rels == []
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("empty_after_filter" in r.message for r in warning_records)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_relations_raises_on_empty_response():
    llm = _StubLLM("")
    with pytest.raises(RelationExtractionError):
        await extract_relations(
            [_entity("A"), _entity("B")], [_post("a", "A", "x")], llm,
        )


@pytest.mark.asyncio
async def test_extract_relations_raises_on_invalid_json():
    # Both the first call and the repair retry must fail for the error to
    # surface; the stub returns the same unparseable content every call.
    llm = _StubLLM("{not an array}")
    with pytest.raises(RelationExtractionError):
        await extract_relations(
            [_entity("A"), _entity("B")], [_post("a", "A", "x")], llm,
        )


@pytest.mark.asyncio
async def test_extract_relations_logs_raw_preview_on_parse_failure(caplog):
    """Diagnosing sim #128 required re-running the pipeline because the
    parser raised without capturing the raw response. The failure path must
    log a preview of what the LLM actually emitted."""
    import logging
    llm = _StubLLM("No meaningful relationships between these entities.")
    with caplog.at_level(logging.WARNING, logger="simswarm.relations"):
        with pytest.raises(RelationExtractionError):
            await extract_relations(
                [_entity("Alice"), _entity("Bob")],
                [_post("alice", "Alice", "x")],
                llm,
            )
    records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("parse_failed" in r.message for r in records)
    assert any("No meaningful relationships" in r.message for r in records)


@pytest.mark.asyncio
async def test_extract_relations_retries_on_parse_failure():
    """If the first response can't be parsed, a repair retry is issued."""
    llm = _StubLLM([
        "No meaningful relationships between these entities.",
        '[{"source": "Alice", "target": "Bob", "type": "SUPPORTS", "fact": "f"}]',
    ])
    rels = await extract_relations(
        [_entity("Alice"), _entity("Bob")],
        [_post("alice", "Alice", "x")],
        llm,
    )
    assert len(llm.calls) == 2
    assert len(rels) == 1
    assert rels[0]["target"] == "Bob"


# ---------------------------------------------------------------------------
# Integration with build_graph
# ---------------------------------------------------------------------------


def test_build_graph_merges_relations_into_edges():
    from simswarm.graph import build_graph

    entities = [_entity("Alice"), _entity("Bob")]
    chat_log = [_post("alice", "Alice", "x")]
    relations = [{"source": "Alice", "target": "Bob", "type": "SUPPORTS",
                  "fact": "Alice endorses Bobs plan."}]
    snapshot = build_graph(entities, chat_log, relations=relations)
    edge_types = {e.get("type") for e in snapshot.edges}
    assert "SUPPORTS" in edge_types
    supports_edge = next(e for e in snapshot.edges if e["type"] == "SUPPORTS")
    assert supports_edge["source"] == "alice"
    assert supports_edge["target"] == "bob"
    assert supports_edge.get("fact") == "Alice endorses Bobs plan."


def test_build_graph_without_relations_is_unchanged():
    """Passing relations=None (the default) must not change existing behaviour."""
    from simswarm.graph import build_graph

    entities = [_entity("Alice"), _entity("Bob")]
    chat_log = [_post("alice", "Alice", "x")]
    a = build_graph(entities, chat_log)
    b = build_graph(entities, chat_log, relations=None)
    assert a.nodes == b.nodes
    assert a.edges == b.edges
