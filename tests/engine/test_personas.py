"""Tests for simswarm.personas — LLM-backed agent persona extraction."""
from __future__ import annotations

import pytest

from simswarm.llm import LLMResponse
from simswarm.personas import PersonaExtractionError, extract_personas


class _StubLLM:
    def __init__(self, content: str):
        self._content = content
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, temperature=0.7):
        self.calls.append({"messages": messages, "temperature": temperature})
        return LLMResponse(content=self._content, tool_calls=[], raw={})

    async def close(self):
        pass


def _profile(agent_id: str, name: str, posts: int = 3) -> dict:
    return {
        "agent_id": agent_id,
        "name": name,
        "posts": posts,
        "actions": posts + 2,
        "rounds_active": posts,
        "platforms": ["twitter"],
        "sample_posts": [f"{name} post {i}" for i in range(posts)],
        "sentiment_arc": "neutral throughout",
    }


@pytest.mark.asyncio
async def test_happy_path_returns_persona_per_agent():
    llm = _StubLLM(
        '{"alice": "A cautious pragmatist.", "bob": "A blunt contrarian."}'
    )
    profiles = [_profile("alice", "Alice"), _profile("bob", "Bob")]
    personas = await extract_personas(profiles, llm, goal="test")
    assert personas == {
        "alice": "A cautious pragmatist.",
        "bob": "A blunt contrarian.",
    }


@pytest.mark.asyncio
async def test_empty_profiles_short_circuits_without_llm_call():
    llm = _StubLLM('{"x": "y"}')
    personas = await extract_personas([], llm)
    assert personas == {}
    assert llm.calls == []


@pytest.mark.asyncio
async def test_missing_agent_in_response_is_absent_from_result():
    llm = _StubLLM('{"alice": "A pragmatist."}')
    profiles = [_profile("alice", "Alice"), _profile("bob", "Bob")]
    personas = await extract_personas(profiles, llm)
    assert personas == {"alice": "A pragmatist."}
    assert "bob" not in personas


@pytest.mark.asyncio
async def test_raises_on_empty_response():
    llm = _StubLLM("")
    with pytest.raises(PersonaExtractionError):
        await extract_personas([_profile("a", "A")], llm)


@pytest.mark.asyncio
async def test_raises_on_invalid_json():
    llm = _StubLLM("{not json}")
    with pytest.raises(PersonaExtractionError):
        await extract_personas([_profile("a", "A")], llm)


@pytest.mark.asyncio
async def test_strips_markdown_fences_from_response():
    llm = _StubLLM('```json\n{"alice": "A pragmatist."}\n```')
    personas = await extract_personas([_profile("alice", "Alice")], llm)
    assert personas == {"alice": "A pragmatist."}


@pytest.mark.asyncio
async def test_non_string_persona_values_are_dropped():
    llm = _StubLLM('{"alice": "A pragmatist.", "bob": 42, "carol": null}')
    profiles = [_profile("alice", "Alice"), _profile("bob", "Bob"),
                _profile("carol", "Carol")]
    personas = await extract_personas(profiles, llm)
    assert personas == {"alice": "A pragmatist."}


@pytest.mark.asyncio
async def test_truncates_overlong_persona():
    llm = _StubLLM('{"alice": "' + "x" * 5000 + '"}')
    personas = await extract_personas([_profile("alice", "Alice")], llm)
    assert len(personas["alice"]) <= 1000
