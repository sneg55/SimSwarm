"""Tests for the Anthropic Messages API adapter."""
from __future__ import annotations

import pytest

from saas.adapters.anthropic_client import AnthropicClient


def test_client_constructs_with_required_fields():
    c = AnthropicClient(api_key="test-key", model="claude-opus-4-6")
    assert c.model == "claude-opus-4-6"
    assert c.api_key == "test-key"


from saas.adapters.anthropic_client import _translate_messages, _translate_tools


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
