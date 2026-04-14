"""Verifies the pod runner enriches profiles.json with LLM personas when
the LLM succeeds, and falls back to the one-liner on failure."""
from __future__ import annotations

from pathlib import Path

import pytest

from simswarm.llm import LLMResponse
from simswarm.types import ActionRecord


class _StubLLM:
    def __init__(self, content: str, *, raise_on_chat: Exception | None = None):
        self._content = content
        self._raise = raise_on_chat
        self.calls: list[dict] = []

    async def chat(self, messages, tools=None, temperature=0.7):
        if self._raise is not None:
            raise self._raise
        self.calls.append({"messages": messages})
        return LLMResponse(content=self._content, tool_calls=[], raw={})

    async def close(self):
        pass


def _post(agent_id: str, agent_name: str, content: str, round_num: int = 1) -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type="create_post", platform="twitter",
        action_args={"text": content}, timestamp="t", success=True,
    )


@pytest.mark.asyncio
async def test_enrich_profiles_with_personas_happy_path(tmp_path: Path):
    from infra.docker.run_job_v2_runner import enrich_profiles_with_personas

    chat_log = [
        _post("alice", "Alice", "pragmatic view on markets", 1),
        _post("bob", "Bob", "contrarian take on tech", 1),
    ]
    profiles = [
        {"agent_id": "alice", "name": "Alice", "persona": "3 posts, 3 actions.",
         "total_posts": 3, "total_actions": 3, "rounds_active": 1, "platforms": ["twitter"]},
        {"agent_id": "bob", "name": "Bob", "persona": "2 posts, 2 actions.",
         "total_posts": 2, "total_actions": 2, "rounds_active": 1, "platforms": ["twitter"]},
    ]
    llm = _StubLLM(
        '{"alice": "A pragmatic voice on markets.", '
        '"bob": "A contrarian technologist."}'
    )
    enriched = await enrich_profiles_with_personas(profiles, chat_log, llm, goal="g")
    by_id = {p["agent_id"]: p for p in enriched}
    assert by_id["alice"]["persona"] == "A pragmatic voice on markets."
    assert by_id["bob"]["persona"] == "A contrarian technologist."


@pytest.mark.asyncio
async def test_enrich_profiles_falls_back_on_llm_error():
    from infra.docker.run_job_v2_runner import enrich_profiles_with_personas

    chat_log = [_post("alice", "Alice", "x", 1)]
    profiles = [
        {"agent_id": "alice", "name": "Alice", "persona": "1 post, 1 action.",
         "total_posts": 1, "total_actions": 1, "rounds_active": 1, "platforms": ["twitter"]},
    ]
    llm = _StubLLM("", raise_on_chat=RuntimeError("network down"))
    enriched = await enrich_profiles_with_personas(profiles, chat_log, llm)
    # One-liner preserved.
    assert enriched[0]["persona"] == "1 post, 1 action."


@pytest.mark.asyncio
async def test_enrich_profiles_falls_back_on_parse_error():
    from infra.docker.run_job_v2_runner import enrich_profiles_with_personas

    chat_log = [_post("alice", "Alice", "x", 1)]
    profiles = [
        {"agent_id": "alice", "name": "Alice", "persona": "1 post, 1 action.",
         "total_posts": 1, "total_actions": 1, "rounds_active": 1, "platforms": ["twitter"]},
    ]
    llm = _StubLLM("{not json}")
    enriched = await enrich_profiles_with_personas(profiles, chat_log, llm)
    assert enriched[0]["persona"] == "1 post, 1 action."


@pytest.mark.asyncio
async def test_enrich_profiles_partial_fallback_for_missing_agent():
    from infra.docker.run_job_v2_runner import enrich_profiles_with_personas

    chat_log = [
        _post("alice", "Alice", "x", 1),
        _post("bob", "Bob", "y", 1),
    ]
    profiles = [
        {"agent_id": "alice", "name": "Alice", "persona": "alice one-liner",
         "total_posts": 1, "total_actions": 1, "rounds_active": 1, "platforms": ["twitter"]},
        {"agent_id": "bob", "name": "Bob", "persona": "bob one-liner",
         "total_posts": 1, "total_actions": 1, "rounds_active": 1, "platforms": ["twitter"]},
    ]
    llm = _StubLLM('{"alice": "Alice persona."}')  # only alice
    enriched = await enrich_profiles_with_personas(profiles, chat_log, llm)
    by_id = {p["agent_id"]: p for p in enriched}
    assert by_id["alice"]["persona"] == "Alice persona."
    assert by_id["bob"]["persona"] == "bob one-liner"
