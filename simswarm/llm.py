"""Async LLM client for OpenAI-compatible APIs.

Direct aiohttp calls — no SDK, no framework.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from simswarm.types import Agent, Observation

logger = logging.getLogger(__name__)

# Transient network errors we retry past. vLLM occasionally drops the
# connection mid-request (worker restart, network jitter); a single drop
# should never kill the whole sim.
_RETRYABLE = (
    aiohttp.ServerDisconnectedError,
    aiohttp.ServerTimeoutError,
    aiohttp.ClientConnectionError,
    asyncio.TimeoutError,
)
_CHAT_MAX_ATTEMPTS = 3
_CHAT_INITIAL_BACKOFF_S = 1.0


@dataclass
class LLMResponse:
    """Parsed response from an LLM call."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def parse_tool_calls(raw: dict) -> list[dict[str, Any]]:
    """Extract tool calls from an OpenAI-format response."""
    message = raw.get("choices", [{}])[0].get("message", {})
    raw_calls = message.get("tool_calls", [])
    results = []
    for call in raw_calls:
        fn = call.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            args = {}
        results.append({"name": name, "args": args})
    return results


def build_context(agent: Agent, observations: list[Observation]) -> list[dict[str, str]]:
    """Assemble the message list for an agent's LLM call."""
    messages = [{"role": "system", "content": agent.persona}]

    # Belief summary
    if agent.belief_state.positions:
        lines = []
        for topic, pos in agent.belief_state.positions.items():
            conf = agent.belief_state.confidence.get(topic, 0.5)
            lines.append(f"- {topic}: position={pos:.2f}, confidence={conf:.2f}")
        messages.append({
            "role": "system",
            "content": "Your current beliefs:\n" + "\n".join(lines),
        })

    # Recent memory
    if agent.memory:
        messages.append({
            "role": "system",
            "content": "Recent actions:\n" + "\n".join(agent.memory[-5:]),
        })

    # Observations
    obs_parts = []
    for obs in observations:
        obs_parts.append(f"[{obs.environment}]\n{obs.content}")
    if obs_parts:
        messages.append({"role": "user", "content": "\n\n".join(obs_parts)})

    return messages


class LLMClient:
    """Async client for OpenAI-compatible /v1/chat/completions."""

    def __init__(self, base_url: str, model: str, api_key: str = "none"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request and return parsed response."""
        session = await self._ensure_session()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_exc: Exception | None = None
        for attempt in range(1, _CHAT_MAX_ATTEMPTS + 1):
            try:
                resp = await session.post(url, json=payload, headers=headers)
                data = await resp.json()
                break
            except _RETRYABLE as exc:
                last_exc = exc
                if attempt == _CHAT_MAX_ATTEMPTS:
                    raise
                backoff = _CHAT_INITIAL_BACKOFF_S * (2 ** (attempt - 1))
                logger.warning(
                    "llm.chat transient error attempt=%d/%d: %s — "
                    "retrying in %.1fs",
                    attempt, _CHAT_MAX_ATTEMPTS, type(exc).__name__, backoff,
                )
                await asyncio.sleep(backoff)
                session = await self._ensure_session()
        else:  # pragma: no cover — unreachable, the for always breaks or raises
            raise last_exc  # type: ignore[misc]

        message = data.get("choices", [{}])[0].get("message", {})
        return LLMResponse(
            content=message.get("content", "") or "",
            tool_calls=parse_tool_calls(data),
            raw=data,
        )

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
