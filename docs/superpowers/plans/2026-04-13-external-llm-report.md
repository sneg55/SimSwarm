# External LLM Report Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move simulation report generation off the GPU pod into a Celery task that calls Claude Opus 4.6 via Anthropic's Messages API, with prompt caching and 100% refund on any pre-`COMPLETED` failure.

**Architecture:** Pod stops calling `generate_report()` and only uploads sim artifacts to MinIO. `run_simulation_task` persists non-report fields, transitions the job to a new `REPORTING` status, and enqueues `generate_report_task`. That task pulls artifacts from MinIO, runs a 5-turn tool loop against a new `AnthropicClient` (matching the existing `LLMClient` interface), and writes the report back to DB + MinIO. Any failure → `FAILED` + full refund. Worker-restart mid-report is handled by extending `recover_stale_jobs` to cover `REPORTING`.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy + asyncpg (async path), psycopg2 (sync Celery path), Celery, Alembic, aiohttp, pytest-asyncio. New dependency: `anthropic` SDK (pinned).

**Reference spec:** `docs/superpowers/specs/2026-04-13-external-llm-report-design.md`

**File structure (new files):**

- `saas/adapters/anthropic_client.py` — `AnthropicClient` with same interface as `simswarm.llm.LLMClient`, plus cache_control on system + tools.
- `saas/jobs/report.py` — `ReportRunner` that pulls artifacts from MinIO and runs the 5-turn loop.
- `saas/jobs/report_tools_minio.py` — `ReportTools` variant over MinIO-sourced JSON dicts.
- `saas/jobs/tasks_report.py` — Celery task `generate_report_task`.
- `saas/storage/minio_download.py` — small read-side helper to fetch artifact bytes by `job_id + filename`.
- `alembic/versions/v3w4x5y6z7a8_add_reporting_status.py` — migration for the new enum value.
- `tests/adapters/test_anthropic_client.py`
- `tests/jobs/test_report_tools_minio.py`
- `tests/jobs/test_report.py`
- `tests/jobs/test_tasks_report.py`
- `tests/jobs/test_tasks_chaining.py`
- `tests/jobs/test_recovery_reporting.py`
- `tests/fixtures/artifacts/small_sim/` — canned real artifacts from a production run

**File structure (modified):**

- `saas/jobs/models.py` — add `REPORTING` to `JobStatus`.
- `saas/jobs/tasks.py` — chain `generate_report_task` after successful sim; fail+refund if `sim_data_uploaded=False`.
- `saas/jobs/recovery.py` — extend to pick up `REPORTING` jobs with no active Celery task.
- `saas/jobs/persistence_sync.py` — add `_transition_to_reporting`, `_save_report_result` helpers.
- `saas/config.py` — `ANTHROPIC_API_KEY`, `SMART_PROVIDER`, `SMART_MODEL`.
- `saas/constants/tiers.py` — `TIER_REPORT_TIMEOUT_S`.
- `infra/docker/run_job_v2.py` — remove `generate_report()` call + `report.md`/`structured_results.json` writes.
- `infra/docker/run_job_v2_runner.py` — remove `generate_report()` function entirely.
- `infra/docker/worker_api.py` — tighten MinIO upload retries; stop returning `report` in `/status`.
- `pyproject.toml` — pin `anthropic` SDK.

---

## Phase 0 — Prep & dependency pinning

### Task 0: Pin the Anthropic SDK and verify local toolchain

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add anthropic to dev dependencies**

Open `pyproject.toml` and locate the main `dependencies` list. Add a single line pin:

```toml
"anthropic==0.39.0",
```

(If the newest stable is already newer when implementing, pin that version — the only hard rule is exact pinning per `feedback_pin_worker_deps`.)

- [ ] **Step 2: Install and verify**

Run: `pip install -e ".[dev]"`
Expected: `Successfully installed anthropic-0.39.0` (or the pinned version).

Run: `python -c "import anthropic; print(anthropic.__version__)"`
Expected: prints the pinned version cleanly.

- [ ] **Step 3: Verify baseline tests still green**

Run: `pytest -x --timeout=60`
Expected: PASS (baseline green — needed so later task-level failures are attributable to the task).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: pin anthropic SDK for external report generation"
```

---

## Phase 1 — AnthropicClient adapter (pure, no DB, no Celery)

### Task 1: Scaffold AnthropicClient with interface parity

**Files:**
- Create: `saas/adapters/anthropic_client.py`
- Test: `tests/adapters/test_anthropic_client.py`

The client must expose the same `chat(messages, tools) → LLMResponse` signature as `simswarm.llm.LLMClient`, so the existing 5-turn loop code stays source-identical when reused. `LLMResponse` is re-exported from `simswarm.llm` — do not redefine.

- [ ] **Step 1: Write the failing test for construction**

Create `tests/adapters/test_anthropic_client.py`:

```python
"""Tests for the Anthropic Messages API adapter."""
from __future__ import annotations

import pytest

from saas.adapters.anthropic_client import AnthropicClient


def test_client_constructs_with_required_fields():
    c = AnthropicClient(api_key="test-key", model="claude-opus-4-6")
    assert c.model == "claude-opus-4-6"
    assert c.api_key == "test-key"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'saas.adapters.anthropic_client'`.

- [ ] **Step 3: Create the minimum file**

Create `saas/adapters/anthropic_client.py`:

```python
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
        raise NotImplementedError  # implemented in subsequent tasks

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
```

- [ ] **Step 4: Confirm the construction test passes**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/adapters/anthropic_client.py tests/adapters/test_anthropic_client.py
git commit -m "feat(adapters): scaffold AnthropicClient with LLMClient-compatible interface"
```

### Task 2: Implement OpenAI → Anthropic message translation

Anthropic's Messages API differs from OpenAI's `/v1/chat/completions` in three important ways the translator must handle:

1. **System prompt** — Anthropic takes it as a top-level `system` field (string or list of content blocks), not as a message with `role: "system"`.
2. **Tool calls from assistant** — Anthropic embeds `tool_use` content blocks inside the assistant message. OpenAI emits a `tool_calls` field on the message.
3. **Tool results** — Anthropic uses `role: "user"` with a `tool_result` content block. OpenAI uses `role: "tool"`.

**Files:**
- Modify: `saas/adapters/anthropic_client.py`
- Modify: `tests/adapters/test_anthropic_client.py`

- [ ] **Step 1: Write failing tests for translation**

Append to `tests/adapters/test_anthropic_client.py`:

```python
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
    # Content is a list of blocks, not a string
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
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: 4 new tests FAIL with `ImportError: cannot import name '_translate_messages'`.

- [ ] **Step 3: Implement the translators**

Append to `saas/adapters/anthropic_client.py` (above the `AnthropicClient` class):

```python
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
    # Map tool_call IDs emitted by the assistant — Anthropic round-trips
    # them in `tool_use_id` on the user-side tool_result block.
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

        # Plain user / plain assistant with string content — pass through
        out.append({"role": role, "content": msg.get("content", "")})
    return system_prompt, out
```

- [ ] **Step 4: Confirm the translation tests pass**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/adapters/anthropic_client.py tests/adapters/test_anthropic_client.py
git commit -m "feat(adapters): translate OpenAI message shapes to Anthropic Messages API"
```

### Task 3: Implement chat() with prompt caching and response parsing

**Files:**
- Modify: `saas/adapters/anthropic_client.py`
- Modify: `tests/adapters/test_anthropic_client.py`

The real API call uses the `anthropic` SDK's async client. For tests, stub the SDK call at the method level rather than mocking HTTP — simpler and more robust against SDK internal changes.

- [ ] **Step 1: Write failing test for a full chat() happy path**

Append to `tests/adapters/test_anthropic_client.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest


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

    # Ensure cache_control was applied to system + tools
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
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: both new tests FAIL (chat raises `NotImplementedError`).

- [ ] **Step 3: Implement chat() and helpers**

Replace the `AnthropicClient` class body in `saas/adapters/anthropic_client.py`:

```python
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

        # Apply cache_control to the LAST system block and LAST tool schema —
        # per Anthropic docs, cache_control on a block caches everything up to
        # and including that block.
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
```

And append the response parser as a module-level function below the class:

```python
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
```

- [ ] **Step 4: Run the adapter tests**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/adapters/anthropic_client.py tests/adapters/test_anthropic_client.py
git commit -m "feat(adapters): AnthropicClient.chat with prompt caching and tool-use parsing"
```

### Task 4: Exception classification test coverage

**Files:**
- Modify: `tests/adapters/test_anthropic_client.py`

- [ ] **Step 1: Add failing tests for error classification**

Append to `tests/adapters/test_anthropic_client.py`:

```python
@pytest.mark.asyncio
async def test_chat_wraps_rate_limit_as_transient(monkeypatch):
    from anthropic import RateLimitError

    client = AnthropicClient(api_key="k", model="claude-opus-4-6")

    async def _raise(*_a, **_kw):
        raise RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
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
            response=MagicMock(status_code=503, headers={}),
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
            response=MagicMock(status_code=400, headers={}),
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
```

- [ ] **Step 2: Run the tests and confirm they pass**

Run: `pytest tests/adapters/test_anthropic_client.py -v`
Expected: all tests PASS (implementation from Task 3 already covers them).

- [ ] **Step 3: Commit**

```bash
git add tests/adapters/test_anthropic_client.py
git commit -m "test(adapters): exception classification coverage for AnthropicClient"
```

---

## Phase 2 — ReportRunner + MinIO-sourced tools (no Celery yet)

### Task 5: Add canned artifact fixtures

Per `feedback_no_fake_data`, artifacts must come from a real production run — not synthesized. Instructions:

1. Run any small-tier sim against staging or prod.
2. Download its MinIO artifacts (four files suffice: `chat_log.json`, `posts.json`, `trades.json`, `agent_trajectories.json`).
3. Copy them verbatim into `tests/fixtures/artifacts/small_sim/`.
4. Redact no content — these are already user-generated simulation data and not PII.

**Files:**
- Create: `tests/fixtures/artifacts/small_sim/chat_log.json`
- Create: `tests/fixtures/artifacts/small_sim/posts.json`
- Create: `tests/fixtures/artifacts/small_sim/trades.json`
- Create: `tests/fixtures/artifacts/small_sim/agent_trajectories.json`
- Create: `tests/fixtures/artifacts/__init__.py` (empty)

- [ ] **Step 1: Copy artifact files from a real sim**

For each file, paste real content into the target path. Each must be valid JSON of the expected type (see `saas/storage/minio_client.py:SIM_DATA_FILES`):

- `chat_log.json` — list of dicts with `{round_num, agent_id, agent_name, action_type, platform, action_args, timestamp, success}` keys.
- `posts.json` — list of dicts with at minimum `{content, agent_name, round_num}`.
- `trades.json` — list of dicts with at minimum `{round_num, agent_id, action}`. Empty list `[]` is acceptable if the sim had no market activity.
- `agent_trajectories.json` — list of `{agent_id, name, rounds: [...]}`.

- [ ] **Step 2: Validate the JSON is well-formed**

Run:
```bash
python -c "import json; [json.loads(open(f'tests/fixtures/artifacts/small_sim/{n}.json').read()) for n in ('chat_log','posts','trades','agent_trajectories')]; print('OK')"
```
Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/artifacts/
git commit -m "test: canned small-sim artifacts from production run"
```

### Task 6: Implement MinIO download helper

**Files:**
- Create: `saas/storage/minio_download.py`
- Modify: `saas/storage/__init__.py` (if re-exports exist; otherwise skip)
- Test: inline in `tests/jobs/test_report_tools_minio.py` later — this module is thin enough.

- [ ] **Step 1: Create the helper**

Create `saas/storage/minio_download.py`:

```python
"""MinIO artifact download helper used by the report task.

Reads sim-data/{job_id}/{filename} via the Minio SDK. Returns bytes.
Separate from the presigned-URL path because the report task runs server-side
and doesn't need URL signing.
"""
from __future__ import annotations

import io
import logging
import os

logger = logging.getLogger(__name__)


class ArtifactMissingError(Exception):
    """Raised when an expected MinIO artifact is absent."""


def fetch_artifact(job_id: int, filename: str) -> bytes:
    """Fetch a single artifact by (job_id, filename).

    Uses MINIO_* env vars (identical set to SimDataStorage). Raises
    ArtifactMissingError on 404.
    """
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        raise ArtifactMissingError(
            f"MINIO_ENDPOINT not set; cannot fetch {filename} for job {job_id}"
        )
    from minio import Minio
    from minio.error import S3Error

    client = Minio(
        endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=os.getenv("MINIO_SECURE", "true").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET", "simswarm")
    obj = f"sim-data/{job_id}/{filename}"

    try:
        resp = client.get_object(bucket, obj)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise ArtifactMissingError(f"{obj} missing in bucket {bucket}") from exc
        raise


def put_report_md(job_id: int, markdown: str) -> None:
    """Upload report.md to sim-data/{job_id}/report.md for downstream consumers."""
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        logger.warning("MINIO_ENDPOINT not set; skipping report.md upload for job %d", job_id)
        return
    from minio import Minio

    client = Minio(
        endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=os.getenv("MINIO_SECURE", "true").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET", "simswarm")
    obj = f"sim-data/{job_id}/report.md"
    body = markdown.encode("utf-8")
    client.put_object(
        bucket, obj, data=io.BytesIO(body), length=len(body),
        content_type="text/markdown",
    )
```

- [ ] **Step 2: Run baseline tests to confirm nothing broke**

Run: `pytest -x --timeout=60`
Expected: PASS (no tests reference the new module yet).

- [ ] **Step 3: Commit**

```bash
git add saas/storage/minio_download.py
git commit -m "feat(storage): MinIO artifact download + report.md upload helpers"
```

### Task 7: ReportTools variant over MinIO-sourced artifacts

**Files:**
- Create: `saas/jobs/report_tools_minio.py`
- Test: `tests/jobs/test_report_tools_minio.py`

Parallel class to `simswarm.report_tools.ReportTools` with the same public surface (`get_top_posts`, `get_coalitions`, `get_agent_summary`, `get_trajectory`, `dispatch`, `tool_schemas`), but backed by dicts loaded from MinIO JSON.

- [ ] **Step 1: Write failing tests**

Create `tests/jobs/test_report_tools_minio.py`:

```python
"""Tests for MinIO-sourced report tools."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from saas.jobs.report_tools_minio import ReportArtifacts, ReportTools

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts" / "small_sim"


def _load_fixture() -> ReportArtifacts:
    return ReportArtifacts(
        chat_log=json.loads((FIXTURE_DIR / "chat_log.json").read_text()),
        posts=json.loads((FIXTURE_DIR / "posts.json").read_text()),
        trades=json.loads((FIXTURE_DIR / "trades.json").read_text()),
        trajectories=json.loads((FIXTURE_DIR / "agent_trajectories.json").read_text()),
    )


def test_get_top_posts_respects_limit():
    tools = ReportTools(_load_fixture())
    out = tools.get_top_posts(limit=3)
    assert len(out) <= 3


def test_get_agent_summary_returns_expected_shape_for_known_agent():
    arts = _load_fixture()
    tools = ReportTools(arts)
    # Pick any agent_id that appears in chat_log
    if not arts.chat_log:
        pytest.skip("fixture chat_log is empty")
    agent_id = arts.chat_log[0]["agent_id"]

    summary = tools.get_agent_summary(agent_id)
    assert set(summary.keys()) == {
        "name", "total_actions", "total_posts", "rounds_active", "sample_posts"
    }
    assert summary["total_actions"] >= 1


def test_get_agent_summary_unknown_agent_returns_zeroes():
    tools = ReportTools(_load_fixture())
    summary = tools.get_agent_summary("does-not-exist")
    assert summary["total_actions"] == 0
    assert summary["total_posts"] == 0
    assert summary["sample_posts"] == []


def test_dispatch_returns_json_string():
    tools = ReportTools(_load_fixture())
    out = tools.dispatch("get_top_posts", {"limit": 2})
    parsed = json.loads(out)
    assert isinstance(parsed, list)


def test_dispatch_unknown_tool_returns_error_json():
    tools = ReportTools(_load_fixture())
    out = tools.dispatch("nope", {})
    assert "Unknown tool" in out


def test_tool_schemas_match_original_shape():
    from simswarm.report_tools import ReportTools as RefTools
    ours = {t["function"]["name"] for t in ReportTools.tool_schemas()}
    theirs = {t["function"]["name"] for t in RefTools.tool_schemas()}
    assert ours == theirs
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/jobs/test_report_tools_minio.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'saas.jobs.report_tools_minio'`.

- [ ] **Step 3: Implement the tool module**

Create `saas/jobs/report_tools_minio.py`:

```python
"""ReportTools variant that queries MinIO-sourced JSON dicts.

Public surface matches simswarm.report_tools.ReportTools exactly so the
5-turn tool loop is source-portable. Only the data source differs.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReportArtifacts:
    """MinIO-sourced artifacts required for report generation.

    Shapes match the JSON written by the pod (see simswarm/extractor.py and
    simswarm/adapter.py for the canonical schemas).
    """
    chat_log: list[dict[str, Any]] = field(default_factory=list)
    posts: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    trajectories: list[dict[str, Any]] = field(default_factory=list)


def _detect_coalitions(chat_log: list[dict[str, Any]]) -> list[dict]:
    """Mutual-follow coalition detection over an already-dict chat log."""
    follows: dict[str, set[str]] = {}
    for row in chat_log:
        if row.get("action_type", "").lower() != "follow":
            continue
        agent = row.get("agent_id", "")
        target = (row.get("action_args") or {}).get("target_id", "")
        if agent and target:
            follows.setdefault(agent, set()).add(target)

    coalitions: list[dict] = []
    seen: set[frozenset] = set()
    for a, a_follows in follows.items():
        for b in a_follows:
            if b in follows and a in follows[b]:
                key = frozenset({a, b})
                if key in seen:
                    continue
                seen.add(key)
                coalitions.append({"members": sorted(key), "type": "mutual_follow"})
    return coalitions


class ReportTools:
    """Query tools over MinIO-sourced ReportArtifacts."""

    def __init__(self, artifacts: ReportArtifacts) -> None:
        self._artifacts = artifacts

    def get_top_posts(self, limit: int = 10) -> list[dict]:
        return self._artifacts.posts[:limit]

    def get_coalitions(self) -> list[dict]:
        return _detect_coalitions(self._artifacts.chat_log)

    def get_agent_summary(self, agent_id: str) -> dict:
        actions = [r for r in self._artifacts.chat_log if r.get("agent_id") == agent_id]
        if not actions:
            return {
                "name": agent_id,
                "total_actions": 0,
                "total_posts": 0,
                "rounds_active": 0,
                "sample_posts": [],
            }
        posts = [r for r in actions if r.get("action_type", "").lower() == "create_post"]
        return {
            "name": actions[0].get("agent_name", agent_id),
            "total_actions": len(actions),
            "total_posts": len(posts),
            "rounds_active": len({r.get("round_num") for r in actions}),
            "sample_posts": [
                (r.get("action_args") or {}).get("content", "") for r in posts[:3]
            ],
        }

    def get_trajectory(self, agent_id: str) -> list[dict]:
        for entry in self._artifacts.trajectories:
            if entry.get("agent_id") == agent_id:
                return entry.get("rounds", [])
        return []

    def dispatch(self, tool_name: str, args: dict) -> str:
        try:
            if tool_name == "get_top_posts":
                return json.dumps(self.get_top_posts(**args))
            if tool_name == "get_coalitions":
                return json.dumps(self.get_coalitions())
            if tool_name == "get_agent_summary":
                return json.dumps(self.get_agent_summary(**args))
            if tool_name == "get_trajectory":
                return json.dumps(self.get_trajectory(**args))
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tool %s raised: %s", tool_name, exc)
            return json.dumps({"error": str(exc)})

    @staticmethod
    def tool_schemas() -> list[dict]:
        # Re-export from the canonical source so the two stay in sync.
        from simswarm.report_tools import ReportTools as RefTools
        return RefTools.tool_schemas()
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/jobs/test_report_tools_minio.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/report_tools_minio.py tests/jobs/test_report_tools_minio.py
git commit -m "feat(jobs): ReportTools variant over MinIO-sourced artifacts"
```

### Task 8: ReportRunner: orchestrates artifact fetch + 5-turn loop

**Files:**
- Create: `saas/jobs/report.py`
- Test: `tests/jobs/test_report.py`

The runner owns:
1. Artifact fetch (via `fetch_artifact`).
2. Instantiating tools + an LLMClient-compatible client.
3. Running the same 5-turn loop as `simswarm.report.ReportGenerator`.
4. Returning a `ReportResult` (report markdown + executive brief + findings) the Celery task persists.

- [ ] **Step 1: Write failing tests**

Create `tests/jobs/test_report.py`:

```python
"""Tests for ReportRunner (the SaaS-side report orchestrator)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from simswarm.llm import LLMResponse
from saas.jobs.report import ReportExhaustedError, ReportRunner

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "artifacts" / "small_sim"


def _canned_fetcher(missing: set[str] | None = None):
    missing = missing or set()

    def _fetch(job_id: int, filename: str) -> bytes:
        if filename in missing:
            from saas.storage.minio_download import ArtifactMissingError
            raise ArtifactMissingError(filename)
        return (FIXTURE_DIR / filename).read_bytes()
    return _fetch


class _StubClient:
    """Scripts a sequence of LLMResponse returns for chat()."""
    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls = 0

    async def chat(self, messages, tools=None, temperature=0.7):
        assert self.script, "StubClient ran out of responses"
        self.calls += 1
        return self.script.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_happy_path_returns_markdown_and_findings():
    script = [
        LLMResponse(content="", tool_calls=[{"id": "c1", "name": "get_top_posts", "args": {"limit": 3}}]),
        LLMResponse(content=(
            "## Executive Summary\n"
            "The simulation showed healthy engagement.\n\n"
            "## Key Findings\n"
            "### Finding 1: Core coalition emerged\n"
            "Agents A and B formed a mutual-follow pair.\n\n"
            "## Conclusion\n"
            "High-confidence result.\n"
        ), tool_calls=[]),
    ]
    runner = ReportRunner(
        job_id=42,
        goal="Test goal",
        client=_StubClient(script),
        fetcher=_canned_fetcher(),
    )
    result = await runner.run()
    assert "Executive Summary" in result.report_markdown
    assert "healthy engagement" in result.executive_brief
    assert len(result.findings) == 1
    assert result.findings[0]["title"] == "Finding 1: Core coalition emerged"


@pytest.mark.asyncio
async def test_missing_required_artifact_raises():
    from saas.jobs.report import ReportArtifactsMissingError
    runner = ReportRunner(
        job_id=42,
        goal="Test",
        client=_StubClient([]),
        fetcher=_canned_fetcher(missing={"chat_log.json"}),
    )
    with pytest.raises(ReportArtifactsMissingError):
        await runner.run()


@pytest.mark.asyncio
async def test_exhausted_loop_raises_without_final_markdown():
    tool_only = LLMResponse(
        content="",
        tool_calls=[{"id": "c1", "name": "get_top_posts", "args": {"limit": 1}}],
    )
    runner = ReportRunner(
        job_id=42,
        goal="Test",
        client=_StubClient([tool_only] * 10),
        fetcher=_canned_fetcher(),
    )
    with pytest.raises(ReportExhaustedError):
        await runner.run()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/jobs/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement ReportRunner**

Create `saas/jobs/report.py`:

```python
"""SaaS-side report runner: loads MinIO artifacts, runs a tool-calling LLM loop.

Mirrors simswarm.report.ReportGenerator behavior but is driven by MinIO-sourced
ReportArtifacts instead of a live SimulationResult. The prompt template is
reused verbatim from simswarm/prompts/report.j2.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from jinja2 import Environment, FileSystemLoader

from saas.jobs.report_tools_minio import ReportArtifacts, ReportTools
from saas.storage.minio_download import ArtifactMissingError, fetch_artifact
from simswarm.llm import LLMResponse

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 5

# Reuse the exact same template the engine ships with so on-pod and off-pod
# reports are identical modulo the backing LLM.
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "simswarm" / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

_REQUIRED_ARTIFACTS = ("chat_log.json", "posts.json", "trades.json", "agent_trajectories.json")


class ReportExhaustedError(Exception):
    """The 5-turn loop ended without a final markdown response."""


class ReportArtifactsMissingError(Exception):
    """A required MinIO artifact could not be fetched."""


class _ChatClient(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = ...,
        temperature: float = ...,
    ) -> LLMResponse: ...
    async def close(self) -> None: ...


@dataclass
class ReportResult:
    report_markdown: str = ""
    executive_brief: str = ""
    findings: list[dict[str, str]] = field(default_factory=list)


class ReportRunner:
    """Orchestrates artifact fetch + multi-turn LLM tool loop for a single job."""

    def __init__(
        self,
        job_id: int,
        goal: str,
        client: _ChatClient,
        fetcher: Callable[[int, str], bytes] = fetch_artifact,
    ) -> None:
        self.job_id = job_id
        self.goal = goal
        self._client = client
        self._fetcher = fetcher

    async def run(self) -> ReportResult:
        artifacts = self._load_artifacts()
        tools = ReportTools(artifacts)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._render_system_prompt()}
        ]
        markdown = ""

        for turn in range(_MAX_ROUNDS):
            response = await self._client.chat(
                messages, tools=ReportTools.tool_schemas()
            )
            if response.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })
                for call in response.tool_calls:
                    result = tools.dispatch(call.get("name", ""), call.get("args", {}))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": result,
                    })
                continue
            markdown = response.content
            break

        if not markdown:
            raise ReportExhaustedError(
                f"Report loop for job {self.job_id} ended without final markdown"
            )

        return ReportResult(
            report_markdown=markdown,
            executive_brief=_extract_brief(markdown),
            findings=_extract_findings(markdown),
        )

    def _load_artifacts(self) -> ReportArtifacts:
        loaded: dict[str, Any] = {}
        for name in _REQUIRED_ARTIFACTS:
            try:
                raw = self._fetcher(self.job_id, name)
            except ArtifactMissingError as exc:
                raise ReportArtifactsMissingError(str(exc)) from exc
            loaded[name] = json.loads(raw.decode("utf-8"))
        return ReportArtifacts(
            chat_log=loaded["chat_log.json"],
            posts=loaded["posts.json"],
            trades=loaded["trades.json"],
            trajectories=loaded["agent_trajectories.json"],
        )

    def _render_system_prompt(self) -> str:
        return _jinja_env.get_template("report.j2").render(goal=self.goal).strip()


def _extract_brief(markdown: str) -> str:
    match = re.search(
        r"##\s+Executive Summary\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _extract_findings(markdown: str) -> list[dict[str, str]]:
    section_match = re.search(
        r"##\s+Key Findings\s*\n+(.*?)(?=\n##|\Z)",
        markdown,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        return []
    findings: list[dict[str, str]] = []
    for block in re.split(r"(?=###\s)", section_match.group(1)):
        block = block.strip()
        if not block:
            continue
        m = re.match(r"###\s+(.+?)\n+(.*)", block, re.DOTALL)
        if m:
            findings.append({"title": m.group(1).strip(), "content": m.group(2).strip()})
    return findings
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/jobs/test_report.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/report.py tests/jobs/test_report.py
git commit -m "feat(jobs): ReportRunner with MinIO artifact loading + 5-turn tool loop"
```

---

## Phase 3 — Schema and config plumbing

### Task 9: Add `REPORTING` to `JobStatus` enum

**Files:**
- Modify: `saas/jobs/models.py:8-16`
- Create: `alembic/versions/v3w4x5y6z7a8_add_reporting_status.py`

- [ ] **Step 1: Add the enum value**

Edit `saas/jobs/models.py`. Find the `JobStatus` enum and insert `REPORTING` between `RUNNING` and `COMPLETED`:

```python
class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
```

- [ ] **Step 2: Create the Alembic migration**

Verify the current head first: `alembic heads` should report `u2v3w4x5y6z7` as the most recent. If a later head has been added since this plan was written, substitute the latest one in `down_revision` below.

Create `alembic/versions/v3w4x5y6z7a8_add_reporting_status.py`:

```python
"""add REPORTING job status

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-04-13
"""
from alembic import op

revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    op.execute("COMMIT")
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'REPORTING' AFTER 'RUNNING'")
    op.execute("BEGIN")


def downgrade() -> None:
    # Postgres does not support removing enum values safely; noop.
    pass
```

- [ ] **Step 3: Verify the migration applies to a disposable Postgres instance**

If you have a dev Postgres available:
```bash
alembic upgrade head
```
Expected: migration runs cleanly, no errors.

If you do not, skip this step — the CI migration job will catch failures.

- [ ] **Step 4: Run the backend tests to confirm the enum change doesn't break anything**

Run: `pytest saas/jobs -v --timeout=60`
Expected: PASS. (In-memory SQLite doesn't care about Postgres enum types — the test suite uses SQLAlchemy-level enum handling.)

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/models.py alembic/versions/v3w4x5y6z7a8_add_reporting_status.py
git commit -m "feat(db): add REPORTING job status + Alembic migration"
```

### Task 10: Add SMART_PROVIDER / SMART_MODEL / ANTHROPIC_API_KEY to Settings

**Files:**
- Modify: `saas/config.py`

- [ ] **Step 1: Extend Settings**

Edit `saas/config.py`. Add these fields after the `XAI_API_KEY` line:

```python
    # External LLM for report generation
    ANTHROPIC_API_KEY: str = ""
    SMART_PROVIDER: str = "anthropic"
    SMART_MODEL: str = "claude-opus-4-6"
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/ -q --timeout=60`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add saas/config.py
git commit -m "feat(config): ANTHROPIC_API_KEY, SMART_PROVIDER, SMART_MODEL settings"
```

### Task 11: Add per-tier report timeouts

**Files:**
- Modify: `saas/constants/tiers.py`

- [ ] **Step 1: Add the constant**

Append to `saas/constants/tiers.py`:

```python
# Wall-clock cap applied inside generate_report_task's own tool loop,
# independent of the GPU-tier timeout (which no longer covers report gen).
TIER_REPORT_TIMEOUT_S = {"small": 300, "medium": 600, "large": 900}
```

- [ ] **Step 2: Commit**

```bash
git add saas/constants/tiers.py
git commit -m "feat(tiers): TIER_REPORT_TIMEOUT_S for external report loop"
```

### Task 12: Sync persistence helpers for report transition + save

**Files:**
- Modify: `saas/jobs/persistence_sync.py`

These helpers must use psycopg2, not the async pool, per `feedback_sync_db_writes`.

- [ ] **Step 1: Inspect the existing file**

Run: `sed -n '1,60p' saas/jobs/persistence_sync.py`

Locate `_save_job_results`. The new helpers follow the same engine-lifecycle pattern (`_get_sync_engine()` → connect → commit → dispose).

- [ ] **Step 2: Append two new helpers to `saas/jobs/persistence_sync.py`**

```python
def _transition_to_reporting(job_id: int) -> None:
    """Move a job from RUNNING → REPORTING.

    Guarded so it's a no-op if the job is already terminal — protects against
    a race where recover_stale_jobs already marked the job failed.
    """
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET status = 'REPORTING' "
                    "WHERE id = :job_id AND status IN ('RUNNING', 'PROVISIONING')"
                ),
                {"job_id": job_id},
            )
            conn.commit()
    finally:
        engine.dispose()


def _save_report_result(
    job_id: int,
    report_markdown: str,
    structured: str,
    key_insight: str | None,
) -> None:
    """Persist final report fields and mark COMPLETED."""
    from sqlalchemy import text
    from datetime import datetime, timezone
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET result_report = :report, "
                    "    result_structured = :structured, "
                    "    key_insight = :key_insight, "
                    "    status = 'COMPLETED', "
                    "    completed_at = :completed_at "
                    "WHERE id = :job_id AND status = 'REPORTING'"
                ),
                {
                    "report": report_markdown,
                    "structured": structured,
                    "key_insight": key_insight,
                    "completed_at": datetime.now(timezone.utc),
                    "job_id": job_id,
                },
            )
            conn.commit()
    finally:
        engine.dispose()
```

- [ ] **Step 3: Re-export from the facade**

Edit `saas/jobs/persistence.py`. Add `_transition_to_reporting` and `_save_report_result` to the import from `persistence_sync` and to `__all__`.

Specifically, modify the import block:

```python
from saas.jobs.persistence_sync import (
    _mark_job_failed_sync,
    _save_job_results,
    _update_job_retry_sync,
    _get_job_status,
    _get_job_config_for_resume,
    _transition_to_reporting,
    _save_report_result,
)
```

And append to `__all__`:

```python
    "_transition_to_reporting",
    "_save_report_result",
```

- [ ] **Step 4: Quick smoke test**

Run: `python -c "from saas.jobs.persistence import _transition_to_reporting, _save_report_result; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Run the backend tests**

Run: `pytest saas/jobs tests/jobs -q --timeout=60`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/persistence_sync.py saas/jobs/persistence.py
git commit -m "feat(persistence): _transition_to_reporting and _save_report_result helpers"
```

---

## Phase 4 — Celery task + chaining

### Task 13: Implement `generate_report_task`

**Files:**
- Create: `saas/jobs/tasks_report.py`
- Test: `tests/jobs/test_tasks_report.py`

The task is synchronous from Celery's perspective but calls `ReportRunner.run()` inside `_run_async`. On permanent failure it marks the job FAILED and refunds via `_refund_credits`. On transient failure it uses Celery's `self.retry` with the retry schedule from the spec.

- [ ] **Step 1: Write failing tests**

Create `tests/jobs/test_tasks_report.py`:

```python
"""Tests for generate_report_task — happy path and refund behavior."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from saas.jobs.tasks_report import generate_report_task


class _DummyRunner:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    async def run(self):
        if self._exc is not None:
            raise self._exc
        return self._result


@pytest.mark.asyncio
async def test_happy_path_persists_and_marks_completed():
    from saas.jobs.report import ReportResult

    result = ReportResult(
        report_markdown="## Executive Summary\nAll went well.\n",
        executive_brief="All went well.",
        findings=[{"title": "F1", "content": "X"}],
    )

    with patch("saas.jobs.tasks_report._build_runner", return_value=_DummyRunner(result=result)), \
         patch("saas.jobs.tasks_report._save_report_result") as save, \
         patch("saas.jobs.tasks_report.put_report_md") as putmd, \
         patch("saas.jobs.tasks_report._load_credits_charged", return_value=30):
        out = generate_report_task.run(job_id=123, user_id="u1")

    assert out["status"] == "completed"
    save.assert_called_once()
    putmd.assert_called_once_with(123, result.report_markdown)


def test_permanent_failure_marks_failed_and_refunds():
    from saas.adapters.anthropic_client import AnthropicPermanentError

    with patch("saas.jobs.tasks_report._build_runner",
               return_value=_DummyRunner(exc=AnthropicPermanentError("bad key"))), \
         patch("saas.jobs.tasks_report._mark_job_failed") as mk_failed, \
         patch("saas.jobs.tasks_report._refund_credits") as refund, \
         patch("saas.jobs.tasks_report._load_credits_charged", return_value=30):
        with pytest.raises(AnthropicPermanentError):
            generate_report_task.run(job_id=123, user_id="u1")

    mk_failed.assert_called_once()
    refund.assert_called_once_with(job_id=123, user_id="u1", credits=30)
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/jobs/test_tasks_report.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the task module**

Create `saas/jobs/tasks_report.py`:

```python
"""Celery task for external-LLM report generation.

Runs after run_simulation_task completes with sim_data_uploaded=True.
Any failure path (permanent or retries-exhausted) marks the job FAILED
and issues a 100% credit refund.
"""
from __future__ import annotations

import logging
import os

from saas.adapters.anthropic_client import (
    AnthropicClient,
    AnthropicPermanentError,
    AnthropicTransientError,
)
from saas.constants.tiers import TIER_REPORT_TIMEOUT_S  # noqa: F401 — used in future
from saas.jobs.persistence import (
    _mark_job_failed,
    _save_report_result,
    _extract_key_insight,
)
from saas.jobs.refund import _refund_credits
from saas.jobs.report import (
    ReportArtifactsMissingError,
    ReportExhaustedError,
    ReportRunner,
)
from saas.storage.minio_download import put_report_md
from saas.workers.celery_app import celery_app
from saas.workers.utils import _run_async

logger = logging.getLogger(__name__)

# Retry schedule: 30s, 120s, 300s, 900s, 1800s — ~55 minute total window.
_RETRY_BACKOFF_S = [30, 120, 300, 900, 1800]


def _build_runner(job_id: int, goal: str) -> ReportRunner:
    client = AnthropicClient(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("SMART_MODEL", "claude-opus-4-6"),
    )
    return ReportRunner(job_id=job_id, goal=goal, client=client)


def _load_credits_charged(job_id: int) -> int:
    """Read credits_charged from the DB so refund uses the authoritative value."""
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return 0
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT credits_charged, goal FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            if not row:
                return 0
            return int(row[0] or 0)
    finally:
        engine.dispose()


def _load_goal(job_id: int) -> str:
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return ""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT goal FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            return row[0] if row and row[0] else ""
    finally:
        engine.dispose()


@celery_app.task(
    name="fishcloud.generate_report",
    bind=True,
    max_retries=len(_RETRY_BACKOFF_S),
)
def generate_report_task(self, job_id: int, user_id: str) -> dict:
    """Run the external-LLM report generation loop for a completed sim.

    On transient errors: retries with escalating backoff, up to 5 attempts.
    On permanent errors or exhausted retries: marks job FAILED, refunds 100%.
    """
    goal = _load_goal(job_id)
    runner = _build_runner(job_id, goal)

    try:
        result = _run_async(runner.run())
    except AnthropicTransientError as exc:
        attempt = self.request.retries
        if attempt < len(_RETRY_BACKOFF_S):
            countdown = _RETRY_BACKOFF_S[attempt]
            logger.warning(
                "report.transient_retry job_id=%d attempt=%d countdown=%ds err=%s",
                job_id, attempt, countdown, exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        _finalize_as_failed(job_id, user_id, f"report_transient_exhausted: {exc}")
        raise
    except (AnthropicPermanentError, ReportArtifactsMissingError, ReportExhaustedError) as exc:
        _finalize_as_failed(job_id, user_id, f"report_generation_failed: {exc}")
        raise

    # Success path
    structured = _build_structured(result)
    key_insight = _extract_key_insight(result.report_markdown)

    _save_report_result(
        job_id=job_id,
        report_markdown=result.report_markdown,
        structured=structured,
        key_insight=key_insight,
    )
    try:
        put_report_md(job_id, result.report_markdown)
    except Exception as exc:  # noqa: BLE001 — non-fatal; DB row is authoritative
        logger.warning("report.minio_upload_failed job_id=%d err=%s", job_id, exc)

    logger.info(
        "report.completed job_id=%d chars=%d findings=%d",
        job_id, len(result.report_markdown), len(result.findings),
    )
    return {"status": "completed", "report_chars": len(result.report_markdown)}


def _finalize_as_failed(job_id: int, user_id: str, reason: str) -> None:
    """Mark failed and refund 100%."""
    _mark_job_failed(job_id=job_id, error_message=reason)
    credits = _load_credits_charged(job_id)
    if credits > 0:
        _refund_credits(job_id=job_id, user_id=user_id, credits=credits)
    logger.warning("report.failed job_id=%d reason=%s refunded=%d", job_id, reason, credits)


def _build_structured(result) -> str:
    """Minimal structured_results.json replacement (no chat/graph here —
    those are already persisted by run_simulation_task)."""
    import json as _json
    return _json.dumps({
        "executive_brief": result.executive_brief,
        "findings": result.findings,
    })
```

- [ ] **Step 4: Register the task module for Celery autodiscovery**

Edit `saas/jobs/tasks.py`. Locate the existing block near the top that re-exports auto-registered tasks (around the `# Import resume + maintenance tasks` comment) and add a line:

```python
from saas.jobs.tasks_report import generate_report_task  # noqa: F401 — re-export
```

- [ ] **Step 5: Run the new tests**

Run: `pytest tests/jobs/test_tasks_report.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/tasks_report.py tests/jobs/test_tasks_report.py saas/jobs/tasks.py
git commit -m "feat(jobs): generate_report_task with retry + 100% refund on failure"
```

### Task 14: Chain `generate_report_task` from `run_simulation_task`

**Files:**
- Modify: `saas/jobs/tasks.py`
- Test: `tests/jobs/test_tasks_chaining.py`

The modified `run_simulation_task`:
1. Still saves non-report fields from the sim result (chat_log, graph_data, etc.) via `_save_job_results`.
2. If `sim_data_uploaded=True`: transitions the job to `REPORTING` and enqueues `generate_report_task`.
3. If `sim_data_uploaded=False`: marks the job FAILED and refunds 100% (upload failure is now fatal — no inline report fallback).

- [ ] **Step 1: Write failing tests**

Create `tests/jobs/test_tasks_chaining.py`:

```python
"""Tests for run_simulation_task → generate_report_task chaining."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from saas.jobs.tasks import run_simulation_task


def _runner_returning(result_dict):
    """A JobRunner stub whose .run() returns the given dict."""
    runner = MagicMock()

    async def _fake_run(config):
        return result_dict
    runner.run.side_effect = _fake_run
    return runner


def _baseline_kwargs():
    return dict(
        job_id=42,
        user_id="u1",
        seed_text="seed",
        goal="g",
        tier="small",
        model_id="m",
        gpu_type="L40S",
        max_rounds=15,
        vllm_args="",
        llm_api_key="k",
        credits_charged=30,
        enrich_web=False,
        target_agents=3,
    )


def test_successful_sim_enqueues_report_task():
    with patch("saas.jobs.tasks.JobRunner") as JR, \
         patch("saas.jobs.tasks._save_job_results") as save, \
         patch("saas.jobs.tasks._update_sim_data_available") as upd_sd, \
         patch("saas.jobs.tasks._transition_to_reporting") as trans, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as enqueue, \
         patch("saas.jobs.tasks._get_gpu_provider"):
        JR.return_value = _runner_returning({
            "report": "",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
            "sim_data_uploaded": True,
            "pod_id": "pod-x",
            "provision_seconds": 30,
            "pipeline_seconds": 60,
        })
        run_simulation_task.run(**_baseline_kwargs())

    save.assert_called_once()
    upd_sd.assert_called_once_with(42, True)
    trans.assert_called_once_with(42)
    enqueue.assert_called_once()
    (args,), _ = enqueue.call_args
    assert args == (42, "u1")


def test_failed_upload_marks_failed_and_refunds_no_report_task():
    with patch("saas.jobs.tasks.JobRunner") as JR, \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._mark_job_failed") as fail, \
         patch("saas.jobs.tasks._refund_credits") as refund, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as enqueue, \
         patch("saas.jobs.tasks._get_gpu_provider"):
        JR.return_value = _runner_returning({
            "report": "",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
            "sim_data_uploaded": False,
            "pod_id": "pod-y",
        })
        run_simulation_task.run(**_baseline_kwargs())

    fail.assert_called_once()
    refund.assert_called_once_with(job_id=42, user_id="u1", credits=30)
    enqueue.assert_not_called()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/jobs/test_tasks_chaining.py -v`
Expected: FAIL (the chaining logic does not exist yet).

- [ ] **Step 3: Modify `run_simulation_task`**

Edit `saas/jobs/tasks.py`. Locate the success block (around lines 139-163 in the existing file) that calls `_save_job_results` and then `_update_sim_data_available`. Replace it with the following (keeping the earlier metadata/timing persistence intact):

```python
        # Persist non-report results to the SimulationJob table
        report = result.get("report", "")  # pod no longer writes this; kept blank
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        structured = result.get("structured", "{}")

        _save_job_results(
            job_id=job_id, report=report, chat_log=chat_log,
            graph_data=graph_data, key_insight=None, structured=structured,
        )

        sim_data_uploaded = result.get("sim_data_uploaded", False)

        if not sim_data_uploaded:
            # Upload failure is fatal under the new flow — no inline report
            # fallback exists. Fail and refund 100%.
            from saas.jobs.persistence import _mark_job_failed
            _mark_job_failed(
                job_id=job_id,
                error_message="sim_data_upload_failed: artifacts missing from MinIO",
            )
            if credits_charged > 0:
                _refund_credits(job_id=job_id, user_id=user_id, credits=credits_charged)
            logger.warning(
                "job.upload_failed_no_report job_id=%d refunded=%d",
                job_id, credits_charged,
            )
            return result

        # Sim artifacts uploaded — transition to REPORTING and enqueue the
        # external-LLM report task.
        from saas.jobs.persistence import _transition_to_reporting
        _update_sim_data_available(job_id, True)
        _transition_to_reporting(job_id)

        import saas.jobs.tasks_report as _tasks_report
        _tasks_report.generate_report_task.apply_async((job_id, user_id))

        logger.info(
            "job.sim_complete_report_enqueued job_id=%d pod_id=%s provision_s=%s pipeline_s=%s",
            job_id, pod_id, provision_seconds, pipeline_seconds,
            extra={"event": "job_sim_complete", "job_id": job_id,
                   "pod_id": pod_id, "duration_s": pipeline_seconds},
        )
        return result
```

Note: keep the `_extract_key_insight` import removal — it's now done by the report task against the real markdown.

- [ ] **Step 4: Update the sync imports block**

At the top of `saas/jobs/tasks.py`, the existing `from saas.jobs.persistence import (...)` block imports `_extract_key_insight` and others. Remove `_extract_key_insight` from that import (it moved to the report task). Keep everything else.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/jobs/test_tasks_chaining.py tests/jobs/test_tasks_report.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `pytest -q --timeout=60`
Expected: PASS. If existing tests relied on `_save_job_results` being called with a non-empty `report` or a populated `key_insight`, those assertions will now fail — update any offending tests to expect `report=""` and `key_insight=None` for the sim-complete phase.

- [ ] **Step 7: Commit**

```bash
git add saas/jobs/tasks.py tests/jobs/test_tasks_chaining.py
git commit -m "feat(jobs): chain generate_report_task after sim completion; upload failure = fatal"
```

---

## Phase 5 — Recovery for REPORTING state

### Task 15: Extend `recover_stale_jobs` to cover REPORTING

Under the 100% refund rule, a worker restart that loses a `REPORTING` job costs the full pod price. Recovery must re-enqueue the report task.

**Files:**
- Modify: `saas/jobs/recovery.py`
- Test: `tests/jobs/test_recovery_reporting.py`

- [ ] **Step 1: Write failing tests**

Create `tests/jobs/test_recovery_reporting.py`:

```python
"""Tests for recover_stale_jobs REPORTING-state recovery."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch


def test_reporting_job_without_active_task_is_re_enqueued():
    """A job stuck in REPORTING with no active Celery task should have its
    report task re-enqueued rather than being failed."""
    # The recovery flow is integration-heavy (real DB queries). At minimum,
    # verify _recover_reporting_jobs() is called from recover_stale_jobs()
    # and re-enqueues via generate_report_task.delay.
    with patch("saas.jobs.recovery._recover_reporting_jobs") as rec_rep, \
         patch("saas.jobs.recovery.create_engine"):
        # create_engine patched to avoid real DB in this unit test
        try:
            from saas.jobs.recovery import recover_stale_jobs
            recover_stale_jobs()
        except Exception:
            pass  # the real fn will fail later; we only care _recover_reporting_jobs is invoked
    rec_rep.assert_called()
```

(An end-to-end DB test is added in Task 17 under integration.)

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest tests/jobs/test_recovery_reporting.py -v`
Expected: FAIL — `_recover_reporting_jobs` doesn't exist yet.

- [ ] **Step 3: Add the recovery sub-function**

Edit `saas/jobs/recovery.py`. Add this function near the top (after `_check_pod_status`):

```python
def _recover_reporting_jobs(conn, now: datetime) -> list[dict]:
    """Re-enqueue generate_report_task for jobs stuck in REPORTING.

    A REPORTING job is considered stuck if its status was last updated
    more than 10 minutes ago (the report task should complete well within
    the 55-minute retry window; 10 minutes of inactivity implies no Celery
    worker is currently executing the task).
    """
    from sqlalchemy import text
    from saas.jobs.tasks_report import generate_report_task

    stuck = list(conn.execute(
        text(
            "SELECT id, user_id "
            "FROM simulation_jobs "
            "WHERE status = 'REPORTING' "
            "  AND (last_heartbeat IS NULL "
            "       OR last_heartbeat < NOW() - INTERVAL '10 minutes')"
        )
    ))
    requeued: list[dict] = []
    for row in stuck:
        job_id, user_id = row[0], row[1]
        try:
            generate_report_task.apply_async((job_id, user_id))
            logger.warning("recover.reporting_requeued job_id=%d user=%s", job_id, user_id)
            requeued.append({"job_id": job_id, "user_id": user_id})
        except Exception as exc:
            logger.error("recover.reporting_requeue_failed job_id=%d err=%s", job_id, exc)
    return requeued
```

- [ ] **Step 4: Wire it into `recover_stale_jobs`**

In `recover_stale_jobs` (same file), locate the `with engine.connect() as conn:` block that processes stale_jobs. Directly after `conn.commit()` at the end of that block, add:

```python
            # Extended coverage: REPORTING-state jobs orphaned by worker restart
            reporting_requeued = _recover_reporting_jobs(conn, now)
            if reporting_requeued:
                logger.warning(
                    "recover.reporting_summary requeued=%d",
                    len(reporting_requeued),
                )
```

And update the returned dict to include the new list:

```python
        result = {
            "stale_jobs": len(stale_jobs),
            "recovered": len(recovered),
            "resumed": len(resumed),
            "reporting_requeued": len(reporting_requeued) if 'reporting_requeued' in locals() else 0,
            "details": recovered,
            "resumed_details": resumed,
        }
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/jobs/test_recovery_reporting.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add saas/jobs/recovery.py tests/jobs/test_recovery_reporting.py
git commit -m "feat(recovery): re-enqueue generate_report_task for orphaned REPORTING jobs"
```

---

## Phase 6 — Pod-side changes

### Task 16: Tighten MinIO upload retries in `worker_api.py`

Under the new flow, upload failure is fatal. Tighten per-file retry from 1 attempt to 3 with 2-second backoff.

**Files:**
- Modify: `infra/docker/worker_api.py:29-54`

- [ ] **Step 1: Replace the upload function**

Edit `infra/docker/worker_api.py`. Replace the existing `_upload_sim_data` function with:

```python
def _upload_sim_data(results_dir, upload_urls):
    """Upload pre-extracted sim data JSON files to MinIO via presigned URLs.

    Retries each file up to 3 times with 2s backoff before giving up.
    Returns True only if ALL files uploaded successfully — under the
    external-report flow, a single failed upload blocks report generation.
    """
    import requests as req
    import time

    attempts_per_file = 3
    backoff_s = 2

    successes = 0
    for filename, url in upload_urls.items():
        filepath = results_dir / filename
        if not filepath.exists():
            print(f"[worker] Skipping {filename} (not produced by pipeline)", flush=True)
            continue
        body = filepath.read_bytes()
        uploaded = False
        for attempt in range(1, attempts_per_file + 1):
            try:
                resp = req.put(
                    url, data=body,
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                if resp.status_code in (200, 204):
                    uploaded = True
                    print(f"[worker] Uploaded {filename} ({len(body)} bytes, attempt {attempt})", flush=True)
                    break
                print(
                    f"[worker] Upload {filename} attempt {attempt}: HTTP {resp.status_code}",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[worker] Upload {filename} attempt {attempt}: {exc}",
                    flush=True,
                )
            if attempt < attempts_per_file:
                time.sleep(backoff_s)
        if uploaded:
            successes += 1
        else:
            print(f"[worker] Upload FAILED for {filename} after {attempts_per_file} attempts", flush=True)

    # All-or-nothing: report success only if every file that existed uploaded.
    produced = sum(1 for fn in upload_urls if (results_dir / fn).exists())
    print(
        f"[worker] Uploaded {successes}/{produced} sim data files "
        f"(requested {len(upload_urls)})",
        flush=True,
    )
    return successes == produced and produced > 0
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/worker_api.py
git commit -m "fix(worker): retry MinIO uploads up to 3x; require all files for success"
```

### Task 17: Stop generating report on the pod (run_job_v2 changes)

**Files:**
- Modify: `infra/docker/run_job_v2.py`
- Modify: `infra/docker/run_job_v2_runner.py`

This is the atomic cutover step. After this commit, the pod no longer produces `report.md` — the new Celery task is the only source of reports.

**Prerequisite check:** Confirm `worker_api.py` calls `run_job_v2.py`, not the v1 `run_job.py`. Run:

```bash
grep -n "run_job" infra/docker/worker_api.py
```

If the output shows `run_job.py` (v1), follow Step 1a. If it shows `run_job_v2.py` (v2), skip to Step 1b.

- [ ] **Step 1a: (Only if worker_api uses run_job.py) Switch worker_api to run_job_v2**

Edit `infra/docker/worker_api.py`. In the `subprocess.Popen` call inside `_run_pipeline`, change `/app/run_job.py` to `/app/run_job_v2.py`. Leave the rest of the flags intact — `run_job_v2.py` accepts the same CLI surface (`--seed-file`, `--goal`, `--max-rounds`, `--target-agents`, `--output-dir`).

- [ ] **Step 1b: Modify `run_job_v2.py` to skip report generation**

Edit `infra/docker/run_job_v2.py`. Locate `run_pipeline()` (around lines 52-73). Replace the body with:

```python
def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
) -> dict:
    """Sim-only pipeline: entities → simulation → write non-report artifacts.

    Report generation has moved to the SaaS-side Celery task
    (saas/jobs/tasks_report.py); the pod no longer writes report.md or
    structured_results.json.
    """
    entities = get_entities(seed_text, goal, target_agents)

    result = asyncio.run(
        run_simulation(seed_text, goal, max_rounds, entities, target_agents)
    )
    print(f"[run_job_v2] Simulation complete: {len(result.chat_log)} actions", flush=True)

    write_results(result, output_dir)

    out = Path(output_dir)
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))
```

Update the import at the top:

```python
from run_job_v2_runner import run_simulation, write_results  # noqa: E402
```

(Removed `generate_report` from the import list.)

- [ ] **Step 2: Update `write_results` to skip report-dependent outputs**

Edit `infra/docker/run_job_v2_runner.py`. Replace the existing `generate_report()` function with a deprecation shim that raises, so any accidental caller fails loudly:

```python
async def generate_report(*_args, **_kwargs):
    raise NotImplementedError(
        "Report generation moved to saas/jobs/tasks_report.py; "
        "the pod should no longer invoke this path."
    )
```

Then replace `write_results()` with:

```python
def write_results(result: SimulationResult, output_dir: str) -> None:
    """Write all sim-side output files to *output_dir*.

    Files: chat_log.json, graph_data.json, posts.json, engagement_summary.json,
           agent_trajectories.json, social_graph.json, trades.json, summary.json.

    Notably NOT written: report.md, structured_results.json — both are produced
    by the external-LLM report task in the Celery worker.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    def _w(name: str, data: object) -> None:
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
        )

    adapted_chat = adapt_chat_log(result.chat_log)
    _w("chat_log.json", adapted_chat)

    adapted_graph = adapt_graph_data(result.graph_data)
    _w("graph_data.json", adapted_graph)

    _w("posts.json", extract_posts(result.chat_log))
    _w("engagement_summary.json", extract_engagement_summary(result.chat_log))
    _w("agent_trajectories.json", extract_agent_trajectories(result.chat_log))
    _w("social_graph.json", extract_social_graph(result.chat_log))
    _w("trades.json", extract_market_data(result.chat_log))

    meta = adapted_graph.get("metadata", {})
    summary = {
        "status": "completed",
        "report_pending": True,
        "chat_log_entries": len(result.chat_log),
        "graph_nodes": meta.get("total_nodes", 0),
        "graph_edges": meta.get("total_edges", 0),
    }
    _w("summary.json", summary)
    print(json.dumps(summary), flush=True)
```

- [ ] **Step 3: Remove the now-unused `adapt_structured` import in `run_job_v2_runner.py`**

At the top of `run_job_v2_runner.py`, the import line looks like:

```python
from simswarm.adapter import adapt_chat_log, adapt_graph_data, adapt_structured  # noqa: E402
```

Drop `adapt_structured`:

```python
from simswarm.adapter import adapt_chat_log, adapt_graph_data  # noqa: E402
```

Also drop the unused `Report` and `ReportGenerator` imports:

```python
# Remove: from simswarm.report import Report, ReportGenerator  # noqa: E402
```

- [ ] **Step 4: Update `worker_api.py` to stop returning `report` in `/status`**

Edit `infra/docker/worker_api.py`. In `job_status()`, remove the `resp["report"] = _job["result"]["report"]` line and the `"report"` key from the result dict in `_run_pipeline`. The pod no longer has a report; Celery generates it.

Specifically, in `_run_pipeline` change:

```python
        with _lock:
            _job["status"] = "completed"
            _job["result"] = {
                "report": report,
                "chat_log": chat_log,
                "graph_data": graph_data,
                "structured": structured,
                "sim_data_uploaded": sim_data_uploaded,
            }
```

to:

```python
        with _lock:
            _job["status"] = "completed"
            _job["result"] = {
                "chat_log": chat_log,
                "graph_data": graph_data,
                "structured": structured,
                "sim_data_uploaded": sim_data_uploaded,
            }
```

Also delete the two lines that read `report.md` and `structured_results.json`:

```python
        # DELETE:
        # if (results_dir / "report.md").exists():
        #     report = (results_dir / "report.md").read_text()
        # ...
        # structured = "{}"
        # if (results_dir / "structured_results.json").exists():
        #     structured = (results_dir / "structured_results.json").read_text()
```

Replace with:

```python
        # The pod no longer generates report.md or structured_results.json —
        # those are produced by the external-LLM Celery task.
        structured = "{}"
```

And in `job_status()`:

```python
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["chat_log"] = _job["result"]["chat_log"]
            resp["graph_data"] = _job["result"].get("graph_data", "{}")
            resp["structured"] = _job["result"].get("structured", "{}")
            resp["sim_data_uploaded"] = _job["result"].get("sim_data_uploaded", False)
        if _job["status"] == "failed":
            resp["error"] = _job["error"]
    return jsonify(resp)
```

- [ ] **Step 5: Update `saas/jobs/pipeline.py` to tolerate missing `report` field**

Edit `saas/jobs/pipeline.py`. In `poll_until_complete` the final return dict accesses `result.get("report", "")` — that's already safe (`.get` with default). No change required; verify by:

```bash
grep -n '"report"' saas/jobs/pipeline.py
```

Expected: the one reference uses `.get("report", "")`.

- [ ] **Step 6: Run the full backend suite**

Run: `pytest -q --timeout=60`
Expected: PASS. If any existing test asserts on the pod returning a `report` field, update it to accept `""`.

- [ ] **Step 7: Commit**

```bash
git add infra/docker/run_job_v2.py infra/docker/run_job_v2_runner.py infra/docker/worker_api.py
git commit -m "feat(worker): stop generating report on pod; structured_results moves off-pod"
```

---

## Phase 7 — Self-review and docs

### Task 18: Spec coverage self-audit

- [ ] **Step 1: Open the spec and this plan side-by-side**

Run:
```bash
diff -y <(grep -E "^(##|###) " docs/superpowers/specs/2026-04-13-external-llm-report-design.md) <(grep -E "^(##|###) " docs/superpowers/plans/2026-04-13-external-llm-report.md) | head -80
```

Verify every spec section (Architecture, Components, Data flow, Refund matrix, Testing, Rollout) has at least one task addressing it.

- [ ] **Step 2: Check for placeholders in the plan**

Run:
```bash
grep -nE "TBD|TODO|FIXME|XXX|implement later|fill in" docs/superpowers/plans/2026-04-13-external-llm-report.md
```
Expected: no matches. Fix any that appear.

- [ ] **Step 3: Verify referenced function names exist in the plan's own tasks**

Spot-check:
- `_transition_to_reporting` — defined in Task 12, used in Task 14.
- `_save_report_result` — defined in Task 12, used in Task 13.
- `_recover_reporting_jobs` — defined in Task 15.
- `ReportArtifactsMissingError` / `ReportExhaustedError` — defined in Task 8.
- `AnthropicTransientError` / `AnthropicPermanentError` — defined in Task 1, raised in Task 3.
- `fetch_artifact` / `put_report_md` — defined in Task 6.

- [ ] **Step 4: Final green-bar run**

Run: `pytest -q --timeout=120`
Expected: PASS.

- [ ] **Step 5: Commit any fixups if needed**

If step 1-3 surfaced gaps, fix inline, then:

```bash
git add docs/superpowers/plans/2026-04-13-external-llm-report.md
git commit -m "docs: self-audit fixups on external-llm-report plan"
```

---

## Phase 8 — Manual / operational verification (post-merge, not CI)

Per `feedback_test_deploys_thoroughly`: the GPU pipeline + MinIO + Anthropic API touchpoints are not fully exercised by unit tests. The three checks below must run on staging before closing the feature out.

### Task 19: Staging verification

- [ ] **Step 1: Small-tier job end-to-end**

1. Submit a small-tier job from the UI.
2. Wait for completion.
3. Check the job row — status should reach `COMPLETED`, `result_report` should be populated, no refund entry should exist.
4. Open the report in the UI and verify it reads coherently.

- [ ] **Step 2: Forced report failure → 100% refund**

1. In the staging `.env`, set `ANTHROPIC_API_KEY=sk-invalid-key-for-test`.
2. Restart the Celery worker so the env is picked up.
3. Submit a small-tier job.
4. After sim completes, watch the Celery logs: the report task should retry 5 times, then fail.
5. Verify the job row ends in `FAILED` with `error_message` containing `report_transient_exhausted`.
6. Verify a `credit_entries` row exists for the full refund.
7. Restore the valid `ANTHROPIC_API_KEY`.

- [ ] **Step 3: Deploy mid-REPORTING**

1. Submit a job, wait until status transitions to `REPORTING`.
2. Redeploy (triggers Celery restart).
3. Wait 10+ minutes for `recover_stale_jobs` beat schedule to fire.
4. Verify the report task was re-enqueued (check `recover.reporting_requeued` log line) and the job eventually reaches `COMPLETED`.

---

## Appendix — Spec cross-reference

| Spec section | Primary task(s) |
|---|---|
| §3 Architecture | 13, 14 |
| §4.1 AnthropicClient | 1, 2, 3, 4 |
| §4.1 ReportRunner | 8 |
| §4.1 ReportTools (MinIO) | 7 |
| §4.1 tasks_report | 13, 14 |
| §4.2 models.py REPORTING enum | 9 |
| §4.2 tasks.py chaining | 14 |
| §4.2 recovery.py extension | 15 |
| §4.2 worker_api retry tightening | 16 |
| §4.2 config.py additions | 10 |
| §4.2 tiers.py additions | 11 |
| §4.2 run_job_v2 removal | 17 |
| §5 Data flow (happy path) | 14, 13 |
| §5.1 Artifact contract | 7, 8, 16 |
| §6 Refund rule + failure modes | 13 (F1, F3, F5), 14 (F4), 15 (F7) |
| §7 Cost model | (informational only — no code) |
| §8 Testing | 4, 5, 7, 8, 13, 14, 15 |
| §9 Rollout | 17 (atomic cutover), 19 (manual verify) |
