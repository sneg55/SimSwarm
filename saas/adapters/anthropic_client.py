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
