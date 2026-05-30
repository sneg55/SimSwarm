"""Test LLM client: tool call parsing, retry logic, context assembly."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import aiohttp
import pytest

from simswarm.llm import LLMClient, build_context, parse_tool_calls
from simswarm.types import Agent, AgentActivityConfig, BeliefState, Observation


class TestParseToolCalls:
    def test_parses_single_tool_call(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "create_post",
                            "arguments": json.dumps({"text": "Hello world"}),
                        }
                    }]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["name"] == "create_post"
        assert calls[0]["args"]["text"] == "Hello world"

    def test_parses_multiple_tool_calls(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [
                        {"function": {"name": "create_post", "arguments": '{"text": "A"}'}},
                        {"function": {"name": "like_post", "arguments": '{"post_id": "p1"}'}},
                    ]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 2

    def test_returns_empty_when_no_tool_calls(self):
        raw = {"choices": [{"message": {"content": "I will do nothing."}}]}
        calls = parse_tool_calls(raw)
        assert calls == []

    def test_handles_malformed_arguments_gracefully(self):
        raw = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "function": {
                            "name": "create_post",
                            "arguments": "not valid json{{{",
                        }
                    }]
                }
            }]
        }
        calls = parse_tool_calls(raw)
        assert len(calls) == 1
        assert calls[0]["args"] == {}


class TestBuildContext:
    def test_includes_persona_as_system_message(self):
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed: post by Bob")]
        messages = build_context(agent, obs)
        assert messages[0]["role"] == "system"
        assert "Alice" in messages[0]["content"]

    def test_includes_observations_as_user_message(self):
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=BeliefState(),
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed: post by Bob")]
        messages = build_context(agent, obs)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("post by Bob" in m["content"] for m in user_msgs)

    def test_includes_belief_summary_when_beliefs_exist(self):
        bs = BeliefState(
            positions={"climate": 0.8},
            confidence={"climate": 0.9},
        )
        agent = Agent(
            id="a1", name="Alice", persona="You are Alice.",
            environments=["social"], belief_state=bs,
            config=AgentActivityConfig(),
        )
        obs = [Observation(environment="social", content="Feed")]
        messages = build_context(agent, obs)
        full_text = " ".join(m["content"] for m in messages)
        assert "climate" in full_text


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_chat_sends_correct_payload(self):
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Hello"}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_response

        client = LLMClient(base_url="http://localhost:8000/v1", model="test-model")
        client.session = mock_session

        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result.content == "Hello"

        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "test-model"
        assert payload["messages"][0]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_chat_retries_on_server_disconnected(self, monkeypatch):
        """vLLM occasionally drops the connection mid-request. A single
        ServerDisconnectedError must not kill the whole sim — sim 126 lost
        90 credits at round 75 because chat had no retry and one drop
        propagated all the way up through engine.run.
        """
        # Mock no-op sleep so the test doesn't block on backoff.
        import asyncio
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        mock_session = AsyncMock()
        ok = AsyncMock()
        ok.status = 200
        ok.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "recovered"}}]
        })
        ok.__aenter__ = AsyncMock(return_value=ok)
        ok.__aexit__ = AsyncMock(return_value=False)
        drop = aiohttp.ServerDisconnectedError()
        mock_session.post = AsyncMock(side_effect=[drop, ok])

        client = LLMClient(base_url="http://localhost:8000/v1", model="m")
        client.session = mock_session
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result.content == "recovered"
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_gives_up_after_max_retries(self, monkeypatch):
        """A genuinely dead endpoint should surface after a bounded number
        of attempts rather than hang forever."""
        import asyncio
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(
            side_effect=aiohttp.ServerDisconnectedError(),
        )
        client = LLMClient(base_url="http://localhost:8000/v1", model="m")
        client.session = mock_session
        with pytest.raises(aiohttp.ServerDisconnectedError):
            await client.chat([{"role": "user", "content": "Hi"}])
        # At least 3 attempts before giving up — catches a single transient.
        assert mock_session.post.call_count >= 3

    @pytest.mark.asyncio
    async def test_chat_passes_tools_when_provided(self):
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"tool_calls": [
                {"function": {"name": "do_thing", "arguments": "{}"}}
            ]}}]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_response

        client = LLMClient(base_url="http://localhost:8000/v1", model="test-model")
        client.session = mock_session

        tools = [{"type": "function", "function": {"name": "do_thing", "parameters": {}}}]
        result = await client.chat([{"role": "user", "content": "Go"}], tools=tools)
        assert len(result.tool_calls) == 1

        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "tools" in payload
