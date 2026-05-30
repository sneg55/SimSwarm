"""Tests for the Anthropic Messages API adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from saas.adapters.anthropic_client import (
    AnthropicClient,
    _translate_messages,
    _translate_tools,
)


def test_client_constructs_with_required_fields():
    c = AnthropicClient(api_key="test-key", model="claude-opus-4-6")
    assert c.model == "claude-opus-4-6"
    assert c.api_key == "test-key"


def test_translate_extracts_system_prompt():
    msgs = [
        {"role": "system", "content": "You are a report writer."},
        {"role": "user", "content": "Write the report."},
    ]
    system, translated = _translate_messages(msgs)
    assert system == "You are a report writer."
    assert translated == [{"role": "user", "content": "Write the report."}]


def test_translate_converts_assistant_tool_calls_to_tool_use_blocks():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        {
            "role": "assistant",
            "content": "Thinking...",
            "tool_calls": [
                {"id": "call_1", "name": "get_top_posts", "args": {"limit": 3}},
            ],
        },
    ]
    _, translated = _translate_messages(msgs)
    assistant = translated[1]
    assert assistant["role"] == "assistant"
    assert isinstance(assistant["content"], list)
    text_block = next(b for b in assistant["content"] if b["type"] == "text")
    tool_block = next(b for b in assistant["content"] if b["type"] == "tool_use")
    assert text_block["text"] == "Thinking..."
    assert tool_block["id"] == "call_1"
    assert tool_block["name"] == "get_top_posts"
    assert tool_block["input"] == {"limit": 3}


def test_translate_converts_tool_role_to_user_tool_result():
    msgs = [
        {"role": "system", "content": "sys"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "t", "args": {}}],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"posts": []}'},
    ]
    _, translated = _translate_messages(msgs)
    tool_msg = translated[-1]
    assert tool_msg["role"] == "user"
    assert tool_msg["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": '{"posts": []}'}
    ]


def test_translate_tools_strips_openai_wrapper():
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_top_posts",
                "description": "Return top posts.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
    ]
    translated = _translate_tools(openai_tools)
    assert translated == [
        {
            "name": "get_top_posts",
            "description": "Return top posts.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
    ]


class _StubContentBlock:
    def __init__(self, type, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_chat_returns_text_and_empty_tool_calls_on_simple_reply(monkeypatch):
    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    fake_response = MagicMock()
    fake_response.content = [_StubContentBlock("text", text="Here is the report.")]
    fake_response.stop_reason = "end_turn"

    messages_create = AsyncMock(return_value=fake_response)
    fake_sdk = MagicMock()
    fake_sdk.messages.create = messages_create

    async def _fake_get_client(self):
        return fake_sdk
    monkeypatch.setattr(AnthropicClient, "_get_client", _fake_get_client)

    response = await client.chat(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "go"},
        ],
        tools=[{
            "type": "function",
            "function": {"name": "t", "description": "", "parameters": {}},
        }],
    )

    assert response.content == "Here is the report."
    assert response.tool_calls == []

    call_kwargs = messages_create.call_args.kwargs
    system = call_kwargs["system"]
    assert isinstance(system, list)
    assert system[0].get("cache_control") == {"type": "ephemeral"}
    tools = call_kwargs["tools"]
    assert tools[-1].get("cache_control") == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_chat_parses_tool_use_blocks_into_tool_calls(monkeypatch):
    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    fake_response = MagicMock()
    fake_response.content = [
        _StubContentBlock("text", text="I will use a tool."),
        _StubContentBlock(
            "tool_use", id="toolu_01", name="get_top_posts", input={"limit": 3}
        ),
    ]
    fake_response.stop_reason = "tool_use"

    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(return_value=fake_response)

    async def _fake_get_client(self):
        return fake_sdk
    monkeypatch.setattr(AnthropicClient, "_get_client", _fake_get_client)

    response = await client.chat(
        messages=[{"role": "user", "content": "go"}],
        tools=[],
    )
    assert response.content == "I will use a tool."
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0] == {
        "id": "toolu_01",
        "name": "get_top_posts",
        "args": {"limit": 3},
    }


def _make_httpx_response(status_code: int) -> httpx.Response:
    """Build a minimal httpx.Response with a request set (required by anthropic SDK 0.94.0)."""
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code=status_code, request=req)


@pytest.mark.asyncio
async def test_chat_wraps_rate_limit_as_transient(monkeypatch):
    from anthropic import RateLimitError

    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    async def _raise(*_a, **_kw):
        raise RateLimitError(
            message="rate limited",
            response=_make_httpx_response(429),
            body=None,
        )

    fake_sdk = MagicMock()
    fake_sdk.messages.create = _raise

    async def _fake_get_client(self):
        return fake_sdk
    monkeypatch.setattr(AnthropicClient, "_get_client", _fake_get_client)

    from saas.adapters.anthropic_client import AnthropicTransientError
    with pytest.raises(AnthropicTransientError):
        await client.chat(messages=[{"role": "user", "content": "go"}])


@pytest.mark.asyncio
async def test_chat_wraps_5xx_as_transient(monkeypatch):
    from anthropic import APIStatusError

    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    async def _raise(*_a, **_kw):
        err = APIStatusError(
            message="server error",
            response=_make_httpx_response(503),
            body=None,
        )
        err.status_code = 503
        raise err

    fake_sdk = MagicMock()
    fake_sdk.messages.create = _raise

    async def _fake_get_client(self):
        return fake_sdk
    monkeypatch.setattr(AnthropicClient, "_get_client", _fake_get_client)

    from saas.adapters.anthropic_client import AnthropicTransientError
    with pytest.raises(AnthropicTransientError):
        await client.chat(messages=[{"role": "user", "content": "go"}])


@pytest.mark.asyncio
async def test_chat_wraps_400_as_permanent(monkeypatch):
    from anthropic import APIStatusError

    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    async def _raise(*_a, **_kw):
        err = APIStatusError(
            message="bad request",
            response=_make_httpx_response(400),
            body=None,
        )
        err.status_code = 400
        raise err

    fake_sdk = MagicMock()
    fake_sdk.messages.create = _raise

    async def _fake_get_client(self):
        return fake_sdk
    monkeypatch.setattr(AnthropicClient, "_get_client", _fake_get_client)

    from saas.adapters.anthropic_client import AnthropicPermanentError
    with pytest.raises(AnthropicPermanentError):
        await client.chat(messages=[{"role": "user", "content": "go"}])
