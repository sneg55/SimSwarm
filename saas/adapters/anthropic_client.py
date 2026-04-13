"""Anthropic Messages API adapter — interface-compatible with simswarm.llm.LLMClient.

The 5-turn report tool loop in saas/jobs/report.py calls `chat(messages, tools)`
and expects an LLMResponse. This adapter translates OpenAI-style inputs into
Anthropic's Messages API format and applies prompt caching to the static
system prompt and tool schemas (cache hits bill at 10% of normal input rate).
"""
from __future__ import annotations

import logging
from typing import Any

from simswarm.llm import LLMResponse

logger = logging.getLogger(__name__)


def _translate_tools(openai_tools: list[dict]) -> list[dict]:
    """Strip OpenAI's `{type: function, function: {...}}` wrapper.

    Anthropic expects `[{name, description, input_schema}]` at the top level.
    """
    out = []
    for t in openai_tools:
        fn = t.get("function", t)
        out.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _translate_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Split out the system prompt and translate message shapes.

    Returns (system_prompt, anthropic_messages).
    """
    system_prompt = ""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            if system_prompt:
                system_prompt += "\n\n" + msg.get("content", "")
            else:
                system_prompt = msg.get("content", "")
            continue

        if role == "assistant" and msg.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            text = msg.get("content") or ""
            if text:
                blocks.append({"type": "text", "text": text})
            for call in msg["tool_calls"]:
                blocks.append({
                    "type": "tool_use",
                    "id": call.get("id", call.get("name", "")),
                    "name": call["name"],
                    "input": call.get("args", {}),
                })
            out.append({"role": "assistant", "content": blocks})
            continue

        if role == "tool":
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                }],
            })
            continue

        out.append({"role": role, "content": msg.get("content", "")})
    return system_prompt, out


class AnthropicTransientError(Exception):
    """Raised for retryable Anthropic failures (rate limit, overload, 5xx, network)."""


class AnthropicPermanentError(Exception):
    """Raised for non-retryable Anthropic failures (invalid request, auth)."""


class AnthropicClient:
    """Async client for Anthropic Messages API with cache_control support.

    Interface mirrors simswarm.llm.LLMClient:
      - chat(messages, tools=None, temperature=0.7) -> LLMResponse
      - close()
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-6",
                 max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._client = None  # lazy construction

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        raise NotImplementedError  # implemented in Task 3

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
