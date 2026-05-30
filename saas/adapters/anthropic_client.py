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

    Behavior notes:
      - System prompt and tool schemas are always marked cache_control=ephemeral.
        On turn 2+ of a multi-turn loop these cache hits cost 10% of the normal
        input rate.
      - The adapter translates message shapes, but does NOT add retry logic —
        that is the Celery task's responsibility.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-6",
                 max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        from anthropic import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        system_prompt, anth_messages = _translate_messages(messages)
        anth_tools = _translate_tools(tools or [])

        system_blocks: list[dict[str, Any]] | None = None
        if system_prompt:
            system_blocks = [{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }]

        cached_tools: list[dict[str, Any]] = []
        for i, tool in enumerate(anth_tools):
            if i == len(anth_tools) - 1:
                cached_tools.append({**tool, "cache_control": {"type": "ephemeral"}})
            else:
                cached_tools.append(tool)

        client = await self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": anth_messages,
        }
        if system_blocks is not None:
            kwargs["system"] = system_blocks
        if cached_tools:
            kwargs["tools"] = cached_tools

        try:
            resp = await client.messages.create(**kwargs)
        except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
            raise AnthropicTransientError(str(exc)) from exc
        except APIStatusError as exc:
            if 500 <= getattr(exc, "status_code", 0) < 600:
                raise AnthropicTransientError(str(exc)) from exc
            raise AnthropicPermanentError(str(exc)) from exc

        return _parse_response(resp)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


def _parse_response(resp: Any) -> LLMResponse:
    """Extract text content and tool calls from an Anthropic Message object."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in resp.content:
        btype = getattr(block, "type", "")
        if btype == "text":
            text_parts.append(getattr(block, "text", "") or "")
        elif btype == "tool_use":
            tool_calls.append({
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "args": getattr(block, "input", {}) or {},
            })
    return LLMResponse(
        content="\n".join(text_parts),
        tool_calls=tool_calls,
        raw={"stop_reason": getattr(resp, "stop_reason", "")},
    )
