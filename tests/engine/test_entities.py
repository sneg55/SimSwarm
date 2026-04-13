"""Tests for simswarm.entities — LLM-backed entity extraction."""
from __future__ import annotations

import pytest

from simswarm.entities import (
    EntityExtractionError,
    _parse_json_array,
    extract_entities,
    fallback_entities,
)
from simswarm.llm import LLMResponse


class _StubLLM:
    def __init__(self, content: str):
        self._content = content

    async def chat(self, messages, tools=None, temperature=0.7):
        return LLMResponse(content=self._content, tool_calls=[], raw={})

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_extract_entities_happy_path():
    llm = _StubLLM(
        '[{"name": "Alice Chen", "type": "person", "summary": "AI safety researcher."}, '
        '{"name": "OpenAI leadership", "type": "organization", "summary": "Execs."}]'
    )
    ents = await extract_entities("seed text", "goal", 5, llm)
    assert len(ents) == 2
    assert ents[0].name == "Alice Chen"
    assert ents[0].id == "alice_chen"
    assert ents[0].type == "person"
    assert "AI safety" in ents[0].summary
    assert ents[1].name == "OpenAI leadership"


@pytest.mark.asyncio
async def test_extract_entities_strips_markdown_fence():
    llm = _StubLLM(
        "Here are the entities:\n```json\n"
        '[{"name": "Bob", "type": "person", "summary": "x"}]\n'
        "```\nThat's all."
    )
    ents = await extract_entities("seed", "goal", 5, llm)
    assert len(ents) == 1
    assert ents[0].name == "Bob"


@pytest.mark.asyncio
async def test_extract_entities_caps_at_count():
    payload = "[" + ",".join(
        f'{{"name": "E{i}", "type": "person", "summary": "s"}}'
        for i in range(20)
    ) + "]"
    llm = _StubLLM(payload)
    ents = await extract_entities("seed", "goal", 3, llm)
    assert len(ents) == 3


@pytest.mark.asyncio
async def test_extract_entities_raises_on_empty_response():
    llm = _StubLLM("")
    with pytest.raises(EntityExtractionError):
        await extract_entities("seed", "goal", 5, llm)


@pytest.mark.asyncio
async def test_extract_entities_raises_on_no_json_array():
    llm = _StubLLM("Sorry, I can't help with that.")
    with pytest.raises(EntityExtractionError):
        await extract_entities("seed", "goal", 5, llm)


@pytest.mark.asyncio
async def test_extract_entities_raises_on_invalid_json():
    llm = _StubLLM("[{name: Alice}")  # invalid JSON
    with pytest.raises(EntityExtractionError):
        await extract_entities("seed", "goal", 5, llm)


@pytest.mark.asyncio
async def test_extract_entities_skips_short_names():
    llm = _StubLLM(
        '[{"name": "A", "type": "person", "summary": "too short"},'
        ' {"name": "Bob", "type": "person", "summary": "ok"}]'
    )
    ents = await extract_entities("seed", "goal", 5, llm)
    assert len(ents) == 1
    assert ents[0].name == "Bob"


def test_fallback_filters_articles_and_short_words():
    seed = "A coalition of tech professionals debates whether AI development should pause."
    ents = fallback_entities(seed, count=5)
    names = [e.name for e in ents]
    # 'A' should be filtered (in _STOP_WORDS)
    assert "A" not in names
    # 'AI' is uppercase, length 2 — filtered by len < 3 rule
    assert "AI" not in names


def test_fallback_returns_at_least_one_entity_even_for_bare_input():
    ents = fallback_entities("lowercase words only here", count=3)
    assert len(ents) == 1
    assert ents[0].name == "Entity"


def test_fallback_dedupes_repeated_names():
    seed = "Jane Doe met Jane Doe again at the Jane Doe conference."
    ents = fallback_entities(seed, count=5)
    names = [e.name for e in ents]
    assert names.count("Jane") == 1
    assert names.count("Doe") == 1


def test_parse_json_array_handles_prose_prefix():
    result = _parse_json_array("OK here you go: [1, 2, 3] done.")
    assert result == [1, 2, 3]


def test_parse_json_array_raises_when_no_brackets():
    with pytest.raises(EntityExtractionError):
        _parse_json_array("no brackets here")
