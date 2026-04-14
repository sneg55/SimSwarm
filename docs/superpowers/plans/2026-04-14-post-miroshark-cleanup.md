# Post-MiroShark Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five post-cutover gaps — per-node sentiment, LLM-backed personas, dislike tally, wizard checkbox scope, duplicated worker-image CI build.

**Architecture:** Two independent PRs. PR 1 enriches simulation output on the pod side (sentiment, personas, dislikes). PR 2 hardens the frontend checkbox and deduplicates the CI worker-image build.

**Tech Stack:** Python 3.11 (pytest-asyncio), Vue 3 (Vitest + @vue/test-utils), GitHub Actions, jinja2 for LLM prompts, existing `simswarm.llm.LLMClient`.

**Spec:** `docs/superpowers/specs/2026-04-14-post-miroshark-cleanup-design.md`
**Deferred issues:** SimSwarm#70 (empty social graph), SimSwarm#71 (job 107 repair).

---

## File Structure

### PR 1 — Sim output quality

- **Create:** `simswarm/personas.py` — LLM-backed persona extraction (mirrors `simswarm/relations.py`)
- **Create:** `simswarm/prompts/extract_personas.j2` — jinja2 prompt template
- **Create:** `tests/engine/test_personas.py` — unit tests for the persona module
- **Modify:** `simswarm/extractor_activity.py` — add `agent_sentiment_from_trajectories` helper
- **Modify:** `simswarm/extractor_posts.py:68,75-89` — wire `num_dislikes` into the tally
- **Modify:** `simswarm/extractor.py` — re-export the new helpers
- **Modify:** `infra/docker/run_job_v2_runner.py:135-175` — call personas + stamp sentiment onto graph nodes in `write_results`
- **Modify:** `tests/engine/test_extractor_profiles_and_top_posts.py` — add dislike-tally test
- **Create:** `tests/engine/test_agent_sentiment.py` — unit test for the sentiment helper

### PR 2 — Frontend + CI safety

- **Modify:** `frontend/src/views/NewSimulation.vue:16-23` — shrink label click target
- **Create:** `frontend/src/views/__tests__/NewSimulation.enrichToggle.test.js` — Vitest component test
- **Modify:** `.github/workflows/deploy.yml` — remove embedded build, trigger via `workflow_run`

Each file has one clear responsibility. `personas.py` is a peer of `relations.py`, not bolted onto `extractor_activity.py`, because it carries I/O and prompt concerns that the other extractors don't.

---

## PR 1 — Simulation Output Quality

Work on branch `fix/simswarm-output-quality`.

### Task 1: Agent sentiment aggregator helper

**Files:**
- Modify: `simswarm/extractor_activity.py` (add new function after `extract_agent_trajectories`)
- Modify: `simswarm/extractor.py` (re-export)
- Create: `tests/engine/test_agent_sentiment.py`

- [ ] **Step 1: Write the failing test**

Create `tests/engine/test_agent_sentiment.py`:

```python
"""Tests for agent_sentiment_from_trajectories — average sentiment per agent."""
from __future__ import annotations

from simswarm.extractor_activity import agent_sentiment_from_trajectories


def test_returns_mean_sentiment_per_agent():
    trajectories = [
        {
            "agent_id": "alice",
            "name": "Alice",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 2, "sentiment": 0.4},
                {"round": 2, "posts": 1, "actions": 3, "sentiment": 0.8},
            ],
        },
        {
            "agent_id": "bob",
            "name": "Bob",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 1, "sentiment": -0.2},
            ],
        },
    ]
    result = agent_sentiment_from_trajectories(trajectories)
    assert result == {"alice": 0.6, "bob": -0.2}


def test_empty_trajectories_returns_empty_dict():
    assert agent_sentiment_from_trajectories([]) == {}


def test_agent_with_no_rounds_is_skipped():
    trajectories = [{"agent_id": "alice", "name": "Alice", "rounds": []}]
    assert agent_sentiment_from_trajectories(trajectories) == {}


def test_missing_sentiment_key_treated_as_zero():
    trajectories = [
        {
            "agent_id": "alice",
            "name": "Alice",
            "rounds": [
                {"round": 1, "posts": 1, "actions": 1},  # no sentiment key
                {"round": 2, "posts": 1, "actions": 1, "sentiment": 0.6},
            ],
        },
    ]
    result = agent_sentiment_from_trajectories(trajectories)
    assert result == {"alice": 0.3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_agent_sentiment.py -v`
Expected: FAIL with `ImportError: cannot import name 'agent_sentiment_from_trajectories'`.

- [ ] **Step 3: Add the helper to `simswarm/extractor_activity.py`**

Append after `_profile_summary` (after line 142):

```python
def agent_sentiment_from_trajectories(
    trajectories: list[dict],
) -> dict[str, float]:
    """Return {agent_id: mean_sentiment} from an agent-trajectory list.

    Sentiments are per-round scores from ``extract_agent_trajectories``.
    Agents with no rounds are skipped; missing per-round sentiment fields
    are treated as 0.0. Returned floats are NOT clamped.
    """
    result: dict[str, float] = {}
    for traj in trajectories:
        rounds = traj.get("rounds") or []
        if not rounds:
            continue
        total = sum(float(r.get("sentiment", 0.0)) for r in rounds)
        result[traj["agent_id"]] = total / len(rounds)
    return result
```

- [ ] **Step 4: Re-export from `simswarm/extractor.py`**

Open `simswarm/extractor.py` and add to the import block (alongside existing `extract_agent_trajectories`):

```python
from simswarm.extractor_activity import (
    agent_sentiment_from_trajectories,
    extract_agent_trajectories,
    extract_engagement_summary,
    extract_profiles,
)
```

And add `"agent_sentiment_from_trajectories"` to the `__all__` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_agent_sentiment.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add simswarm/extractor_activity.py simswarm/extractor.py tests/engine/test_agent_sentiment.py
git commit -m "feat(extractors): add agent_sentiment_from_trajectories helper"
```

---

### Task 2: Stamp sentiment onto graph nodes in `write_results`

**Files:**
- Modify: `infra/docker/run_job_v2_runner.py:135-175` (the `write_results` function)
- Create: `tests/engine/test_write_results_sentiment.py`

The plan: compute trajectories once, derive `sentiment_by_agent`, then walk the adapted graph's nodes and stamp `node["sentiment"]` where the node id matches an agent id. `_adapt_node` already reads `n.get("sentiment", 0.0)`, so downstream just works.

- [ ] **Step 1: Write the failing integration test**

Create `tests/engine/test_write_results_sentiment.py`:

```python
"""Verifies write_results stamps per-agent sentiment onto graph nodes."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from simswarm.types import ActionRecord


def _post(agent_id: str, agent_name: str, content: str, round_num: int) -> ActionRecord:
    return ActionRecord(
        round_num=round_num, agent_id=agent_id, agent_name=agent_name,
        action_type="create_post", platform="twitter",
        action_args={"text": content}, timestamp="t", success=True,
    )


def test_write_results_stamps_sentiment_onto_agent_nodes(tmp_path: Path):
    from infra.docker.run_job_v2_runner import write_results

    # Positive words are scored > 0 by score_sentiment.
    chat_log = [
        _post("alice", "Alice", "great wonderful excellent success", 1),
        _post("alice", "Alice", "happy love fantastic win", 2),
        _post("bob", "Bob", "terrible awful failure disaster", 1),
    ]

    # Minimal graph_data with nodes keyed by agent_id, matching the native
    # engine's post-adapter shape (id=agent_id, label=agent_name).
    graph_data = {
        "nodes": [
            {"id": "alice", "label": "Alice", "group": "person"},
            {"id": "bob", "label": "Bob", "group": "person"},
            {"id": "topic-x", "label": "TopicX", "group": "topic"},
        ],
        "edges": [],
        "metadata": {"total_nodes": 3, "total_edges": 0},
    }

    result = SimpleNamespace(chat_log=chat_log, graph_data=graph_data, trajectories={})

    write_results(result, str(tmp_path))

    graph = json.loads((tmp_path / "graph_data.json").read_text())
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    assert nodes_by_id["alice"]["sentiment"] > 0.0
    assert nodes_by_id["bob"]["sentiment"] < 0.0
    # Non-agent nodes keep whatever they had (no sentiment key, or unchanged).
    assert nodes_by_id["topic-x"].get("sentiment", 0.0) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_write_results_sentiment.py -v`
Expected: FAIL — Alice's sentiment is 0.0 (not stamped).

- [ ] **Step 3: Modify `write_results` in `infra/docker/run_job_v2_runner.py`**

Replace the imports block (lines 22-32) — add `agent_sentiment_from_trajectories`:

```python
from simswarm.adapter import adapt_chat_log, adapt_graph_data  # noqa: E402
from simswarm.engine import Engine  # noqa: E402
from simswarm.extractor import (  # noqa: E402
    agent_sentiment_from_trajectories,
    extract_agent_trajectories,
    extract_engagement_summary,
    extract_market_data,
    extract_posts,
    extract_profiles,
    extract_social_graph,
    extract_top_posts,
)
```

Then replace the body of `write_results` starting at line 152. The relevant block becomes:

```python
    adapted_chat = adapt_chat_log(result.chat_log)
    _w("chat_log.json", adapted_chat)

    adapted_graph = adapt_graph_data(result.graph_data)

    trajectories = extract_agent_trajectories(result.chat_log)
    sentiment_by_agent = agent_sentiment_from_trajectories(trajectories)
    # Stamp mean-per-agent sentiment onto matching graph nodes so the
    # frontend GraphCanvas can color them. _adapt_node reads this field.
    for node in adapted_graph.get("nodes", []):
        nid = node.get("id")
        if nid in sentiment_by_agent:
            node["sentiment"] = sentiment_by_agent[nid]

    _w("graph_data.json", adapted_graph)

    _w("posts.json", extract_posts(result.chat_log))
    _w("top_posts.json", extract_top_posts(result.chat_log))
    _w("profiles.json", extract_profiles(result.chat_log))
    _w("engagement_summary.json", extract_engagement_summary(result.chat_log))
    _w("agent_trajectories.json", trajectories)
    _w("social_graph.json", extract_social_graph(result.chat_log))
    _w("trades.json", extract_market_data(result.chat_log))
    _w("relations.json", (result.trajectories or {}).get("relations", []))
```

Note: `trajectories` is now computed once and reused — previously `extract_agent_trajectories(result.chat_log)` ran again for the `agent_trajectories.json` write.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_write_results_sentiment.py -v`
Expected: PASS.

- [ ] **Step 5: Confirm existing tests still pass**

Run: `pytest tests/engine/ -v`
Expected: all existing tests pass (no regressions in extractor tests).

- [ ] **Step 6: Commit**

```bash
git add infra/docker/run_job_v2_runner.py tests/engine/test_write_results_sentiment.py
git commit -m "feat(graph): stamp per-agent sentiment onto graph nodes"
```

---

### Task 3: Dislike tally in top-posts extractor

**Files:**
- Modify: `simswarm/extractor_posts.py:75-95`
- Modify: `tests/engine/test_extractor_profiles_and_top_posts.py`

- [ ] **Step 1: Write the failing test**

Open `tests/engine/test_extractor_profiles_and_top_posts.py`. Append a new test (matching the file's existing conventions — SAMPLE_LOG style, class-based if that's how the file is organised):

```python
def test_top_posts_tallies_dislikes():
    """Vote actions with value=-1 increment num_dislikes on the target post."""
    from simswarm.extractor import extract_top_posts
    from simswarm.types import ActionRecord

    post = ActionRecord(
        round_num=1, agent_id="alice", agent_name="Alice",
        action_type="create_post", platform="twitter",
        action_args={"post_id": "p1", "text": "claim"},
        timestamp="t", success=True,
    )
    dislike = ActionRecord(
        round_num=1, agent_id="bob", agent_name="Bob",
        action_type="vote", platform="twitter",
        action_args={"post_id": "p1", "value": -1},
        timestamp="t", success=True,
    )
    like = ActionRecord(
        round_num=1, agent_id="carol", agent_name="Carol",
        action_type="vote", platform="twitter",
        action_args={"post_id": "p1", "value": 1},
        timestamp="t", success=True,
    )
    top = extract_top_posts([post, dislike, like])
    assert len(top) == 1
    assert top[0]["num_dislikes"] == 1
    assert top[0]["num_likes"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_extractor_profiles_and_top_posts.py::test_top_posts_tallies_dislikes -v`
Expected: FAIL — `num_dislikes == 0`.

- [ ] **Step 3: Modify `extract_top_posts` in `simswarm/extractor_posts.py`**

Replace the aggregation block (lines 75-95) with:

```python
    likes: dict[str, int] = defaultdict(int)
    dislikes: dict[str, int] = defaultdict(int)
    shares: dict[str, int] = defaultdict(int)
    comments: dict[str, int] = defaultdict(int)
    for record in chat_log:
        args = record.action_args or {}
        target = str(args.get("post_id") or args.get("target_id") or "")
        if not target:
            continue
        t = record.action_type.lower()
        if t in ("like_post", "like"):
            likes[target] += 1
        elif t == "vote":
            # Native social env encodes vote direction in args["value"]:
            # +1 is a like, -1 is a dislike. See environments/social.py:142.
            try:
                value = int(args.get("value", 0))
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                likes[target] += 1
            elif value < 0:
                dislikes[target] += 1
        elif t in ("repost", "retweet", "share"):
            shares[target] += 1
        elif t in ("create_comment", "comment", "reply"):
            comments[target] += 1

    for p in posts:
        pid = p["post_id"]
        p["num_likes"] = likes.get(pid, 0)
        p["num_dislikes"] = dislikes.get(pid, 0)
        p["num_shares"] = shares.get(pid, 0) + comments.get(pid, 0)
        p["engagement"] = p["num_likes"] + p["num_shares"]
```

Note: engagement still excludes dislikes — a dislike is not engagement for ranking purposes.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_extractor_profiles_and_top_posts.py -v`
Expected: all tests pass, including the new one.

- [ ] **Step 5: Commit**

```bash
git add simswarm/extractor_posts.py tests/engine/test_extractor_profiles_and_top_posts.py
git commit -m "feat(extractors): tally dislikes from vote actions"
```

---

### Task 4: LLM-backed persona extraction module

**Files:**
- Create: `simswarm/personas.py`
- Create: `simswarm/prompts/extract_personas.j2`
- Create: `tests/engine/test_personas.py`

The module mirrors `simswarm/relations.py`: async function, jinja2 prompt, JSON-object response, defensive parsing, typed error class. Output maps `agent_id → persona_text`.

- [ ] **Step 1: Write the jinja2 prompt template**

Create `simswarm/prompts/extract_personas.j2`:

```
You are writing concise two-to-three sentence personas for agents in a multi-agent simulation. Each persona should capture the agent's stance, tone, and topical focus as evidenced by their posts. Avoid meta-commentary or mention of the simulation itself.

Simulation goal: {{ goal }}

Agents (key = agent_id):
{% for a in agents %}
- id: {{ a.agent_id }}
  name: {{ a.name }}
  platforms: {{ a.platforms | join(", ") }}
  activity: {{ a.posts }} posts, {{ a.actions }} actions across {{ a.rounds_active }} rounds
  sentiment_arc: {{ a.sentiment_arc }}
  sample_posts:
    {% for p in a.sample_posts %}- {{ p }}
    {% endfor %}
{% endfor %}

Write one persona per agent. Respond with ONLY a JSON object mapping agent_id → persona_text (no prose, no markdown fences).

Example:
{
  "alice": "A pragmatic economist who opens with cautious optimism about monetary policy and sharpens into direct criticism as the discussion narrows.",
  "bob": "A contrarian technologist who frames every exchange as a challenge to prevailing assumptions, favouring blunt claims over qualifications."
}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/engine/test_personas.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/engine/test_personas.py -v`
Expected: ImportError on `simswarm.personas` — module doesn't exist.

- [ ] **Step 4: Create `simswarm/personas.py`**

```python
"""LLM-backed agent persona extraction from simulation activity.

Companion to simswarm.relations: where `extract_relations` produces
typed edges, this module produces one 2–3 sentence persona per agent
to replace the one-line activity summary that `extract_profiles` emits
by default.

Callers invoke `extract_personas(...)` once all other extractors have
run (so the sample posts and sentiment arcs are available) and then
merge the returned dict into the `profiles.json` payload. On any
failure the caller is expected to fall back to the existing one-liner.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from simswarm.llm import LLMClient

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=False,
)

_MAX_PERSONA_CHARS = 1000


class PersonaExtractionError(Exception):
    """Raised when the LLM response cannot be parsed into personas."""


async def extract_personas(
    profiles: list[dict],
    llm: LLMClient,
    *,
    goal: str = "",
) -> dict[str, str]:
    """Ask the LLM for a 2–3 sentence persona per agent.

    *profiles* is a list of dicts with at minimum:
      agent_id, name, posts, actions, rounds_active, platforms,
      sample_posts (list[str]), sentiment_arc (str).

    Returns a dict mapping agent_id -> persona_text. Agents missing
    from the response, or with non-string values, are dropped silently
    (caller falls back to the one-liner for them).

    Short-circuits with {} if *profiles* is empty.
    """
    if not profiles:
        return {}

    prompt = _jinja_env.get_template("extract_personas.j2").render(
        agents=profiles,
        goal=goal,
    ).strip()

    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,  # slightly warmer than relations — these are descriptive
    )

    raw = (response.content or "").strip()
    if not raw:
        raise PersonaExtractionError("LLM returned empty response")

    data = _parse_json_object(raw)
    if not isinstance(data, dict):
        raise PersonaExtractionError(
            f"Expected JSON object, got {type(data).__name__}"
        )

    result: dict[str, str] = {}
    valid_ids = {p["agent_id"] for p in profiles}
    for agent_id, persona in data.items():
        if agent_id not in valid_ids:
            continue
        if not isinstance(persona, str):
            continue
        cleaned = persona.strip()
        if not cleaned:
            continue
        result[agent_id] = cleaned[:_MAX_PERSONA_CHARS]

    logger.info("personas.extracted count=%d requested=%d",
                len(result), len(profiles))
    return result


def _parse_json_object(text: str):
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise PersonaExtractionError("No JSON object found in LLM response")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise PersonaExtractionError(f"Invalid JSON: {exc}") from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_personas.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add simswarm/personas.py simswarm/prompts/extract_personas.j2 tests/engine/test_personas.py
git commit -m "feat(simswarm): LLM-backed persona extraction module"
```

---

### Task 5: Wire personas into the pod runner

**Files:**
- Modify: `infra/docker/run_job_v2_runner.py` — call personas after extract_profiles and merge
- Create: `tests/engine/test_write_results_personas.py`

The pod runner currently calls `extract_profiles(result.chat_log)` and writes the result as `profiles.json`. We insert an async persona-enrichment step between those, building `sample_posts` and `sentiment_arc` from already-computed artifacts. On `PersonaExtractionError` or any unexpected exception we keep the one-liner persona — the job must never fail because of this.

- [ ] **Step 1: Write the failing test**

Create `tests/engine/test_write_results_personas.py`:

```python
"""Verifies the pod runner enriches profiles.json with LLM personas when
the LLM succeeds, and falls back to the one-liner on failure."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_write_results_personas.py -v`
Expected: ImportError on `enrich_profiles_with_personas`.

- [ ] **Step 3: Add `enrich_profiles_with_personas` to the pod runner**

Open `infra/docker/run_job_v2_runner.py`. Add imports at the top of the simswarm import block (around line 35):

```python
from simswarm.personas import (  # noqa: E402
    PersonaExtractionError,
    extract_personas,
)
```

Add this new helper after the existing `run_simulation` function (and before the `generate_report` shim, around line 119):

```python
async def enrich_profiles_with_personas(
    profiles: list[dict],
    chat_log: list,
    llm: LLMClient,
    *,
    goal: str = "",
    max_sample_posts: int = 5,
) -> list[dict]:
    """Mutate *profiles* in place with LLM-generated personas.

    On any failure (extraction error, unexpected exception, partial
    response) the original one-liner persona is preserved for the
    affected agent. Returns the same list for caller convenience.
    """
    if not profiles or not chat_log:
        return profiles

    from simswarm.extractor_common import is_post, post_text
    from simswarm.extractor import extract_agent_trajectories

    # Build sample posts per agent: up to *max_sample_posts*, spread across rounds.
    samples: dict[str, list[str]] = {}
    for record in chat_log:
        if not is_post(record.action_type):
            continue
        text = post_text(record.action_args)
        if not text:
            continue
        lst = samples.setdefault(record.agent_id, [])
        if len(lst) < max_sample_posts:
            lst.append(text[:400])

    # Build a coarse sentiment-arc label from trajectories.
    arc_by_agent: dict[str, str] = {}
    for traj in extract_agent_trajectories(chat_log):
        rounds = traj.get("rounds") or []
        if not rounds:
            continue
        scores = [float(r.get("sentiment", 0.0)) for r in rounds]
        first, last = scores[0], scores[-1]
        if abs(last - first) < 0.15:
            arc = f"roughly steady around {sum(scores) / len(scores):+.2f}"
        elif last > first:
            arc = f"moves from {first:+.2f} to {last:+.2f} (upward)"
        else:
            arc = f"moves from {first:+.2f} to {last:+.2f} (downward)"
        arc_by_agent[traj["agent_id"]] = arc

    payload = [
        {
            "agent_id": p["agent_id"],
            "name": p["name"],
            "posts": p.get("total_posts", 0),
            "actions": p.get("total_actions", 0),
            "rounds_active": p.get("rounds_active", 0),
            "platforms": p.get("platforms", []),
            "sample_posts": samples.get(p["agent_id"], []),
            "sentiment_arc": arc_by_agent.get(p["agent_id"], "no activity recorded"),
        }
        for p in profiles
    ]

    try:
        personas = await extract_personas(payload, llm, goal=goal)
    except PersonaExtractionError as exc:
        print(f"personas.extraction_failed: {exc}", flush=True)
        return profiles
    except Exception as exc:  # pragma: no cover - defensive; never fail the job
        print(f"personas.unexpected_error: {exc!r}", flush=True)
        return profiles

    for p in profiles:
        persona = personas.get(p["agent_id"])
        if persona:
            p["persona"] = persona
    return profiles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_write_results_personas.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire into `run_simulation` so personas land in `profiles.json`**

In the same file, the pod currently splits `run_simulation` (async) from `write_results` (sync). The LLM client lives inside `run_simulation` and is closed there. Simplest wiring: do the persona enrichment inside `run_simulation` (where `smart_llm` is already open) and stash the enriched profiles on the result.

Modify `run_simulation` — after the `relations` block (around line 114), before the `return result` in the `try:` branch:

```python
        # Enrich the profiles list with LLM-generated personas. On any
        # failure we keep the one-line activity summary per-agent.
        profiles = extract_profiles(result.chat_log)
        try:
            profiles = await enrich_profiles_with_personas(
                profiles, result.chat_log, smart_llm, goal=goal,
            )
        except Exception as exc:  # pragma: no cover
            print(f"personas.wiring_error: {exc!r}", flush=True)
        result.trajectories = {
            **(result.trajectories or {}),
            "relations": relations,
            "profiles": profiles,
        }
        return result
```

Add `extract_profiles` to the imports if not already there (it is — line 29).

Delete the existing `result.trajectories = {...}` line at ~113 (it's now merged above).

Modify `write_results` — replace the `extract_profiles` call (line 160) so it prefers the pre-enriched profiles:

```python
    enriched_profiles = (result.trajectories or {}).get("profiles")
    if enriched_profiles is None:
        enriched_profiles = extract_profiles(result.chat_log)
    _w("profiles.json", enriched_profiles)
```

This keeps `write_results` usable from tests that don't involve the LLM (which pass a `SimpleNamespace` with `trajectories={}`).

- [ ] **Step 6: Run all engine tests to confirm no regressions**

Run: `pytest tests/engine/ -v`
Expected: all pass, including the two new files from Tasks 2 and 5.

- [ ] **Step 7: Commit**

```bash
git add infra/docker/run_job_v2_runner.py tests/engine/test_write_results_personas.py
git commit -m "feat(jobs): enrich agent profiles with LLM-generated personas"
```

---

### Task 6: Open PR 1

- [ ] **Step 1: Push the branch**

```bash
git push -u origin fix/simswarm-output-quality
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "Sim output quality: sentiment, personas, dislikes" --body "$(cat <<'EOF'
## Summary

Three independent pod-side improvements to post-MiroShark simulation output.

- **Per-node sentiment** — `write_results` now stamps mean-per-agent sentiment onto graph nodes. `_adapt_node` in `graph_adapter.py` already reads `n.get("sentiment", 0.0)`, so the graph canvas starts coloring nodes with no frontend change.
- **LLM-backed personas** — new `simswarm/personas.py` module (peer of `relations.py`). One batched LLM call per sim. On any failure the original one-line activity summary is preserved per-agent.
- **Dislike tally** — `extract_top_posts` now reads `vote` actions with `value=-1` and surfaces `num_dislikes`. Engagement ranking unchanged.

Spec: `docs/superpowers/specs/2026-04-14-post-miroshark-cleanup-design.md`.

## Test plan

- [x] `pytest tests/engine/test_agent_sentiment.py`
- [x] `pytest tests/engine/test_write_results_sentiment.py`
- [x] `pytest tests/engine/test_extractor_profiles_and_top_posts.py`
- [x] `pytest tests/engine/test_personas.py`
- [x] `pytest tests/engine/test_write_results_personas.py`
- [x] `pytest tests/engine/` full engine suite green
- [ ] Smoke one real sim post-merge: confirm Agents tab shows multi-sentence personas, graph nodes render in color, top posts with vote actions show non-zero dislikes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Record the PR URL**

Note the PR URL for your handoff / session notes.

---

## PR 2 — Frontend + CI Safety

Work on branch `fix/wizard-and-ci-cleanup`. Do **not** start this until PR 1 has been green in CI for at least one run.

### Task 7: Shrink enrich-web checkbox click target

**Files:**
- Modify: `frontend/src/views/NewSimulation.vue:16-23`
- Create: `frontend/src/views/__tests__/NewSimulation.enrichToggle.test.js`

- [ ] **Step 1: Write the failing Vitest component test**

Create `frontend/src/views/__tests__/NewSimulation.enrichToggle.test.js`:

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'

// The view imports createJob/getBalance etc. Stub them so the component mounts.
vi.mock('../../api/jobs.js', () => ({
  createJob: vi.fn(), createDraft: vi.fn(), updateDraft: vi.fn(),
  launchDraft: vi.fn(), getJob: vi.fn(),
}))
vi.mock('../../api/billing.js', () => ({ getBalance: vi.fn().mockResolvedValue({ balance: 100 }) }))

async function mountView() {
  const NewSimulation = (await import('../NewSimulation.vue')).default
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: NewSimulation }],
  })
  router.push('/')
  await router.isReady()
  return mount(NewSimulation, { global: { plugins: [router, createPinia()] } })
}

describe('NewSimulation step 1 — enrichWeb toggle surface', () => {
  it('clicking the description paragraph does NOT toggle enrichWeb', async () => {
    const wrapper = await mountView()
    // Default is true (see script setup: const enrichWeb = ref(true)).
    const initial = wrapper.vm.enrichWeb
    expect(initial).toBe(true)
    const desc = wrapper.find('p.text-xs.text-mist-slate')
    expect(desc.exists()).toBe(true)
    await desc.trigger('click')
    expect(wrapper.vm.enrichWeb).toBe(initial)
  })

  it('clicking the title span still toggles enrichWeb', async () => {
    const wrapper = await mountView()
    const initial = wrapper.vm.enrichWeb
    const title = wrapper.find('label span')
    expect(title.exists()).toBe(true)
    await title.trigger('click')
    // Toggle occurs via the <label>'s native checkbox association.
    expect(wrapper.vm.enrichWeb).toBe(!initial)
  })
})
```

Note: `enrichWeb` needs to be exposed on the component instance for the test. Vue 3 `<script setup>` components expose refs via `defineExpose`. See Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- NewSimulation.enrichToggle`
Expected: FAIL — the description click currently toggles the checkbox because it's inside the `<label>`.

- [ ] **Step 3: Modify `NewSimulation.vue` template and expose the ref**

Replace lines 16-23 (the `<label>` block) with:

```html
      <div class="flex items-center gap-3 mt-4">
        <label class="flex items-center gap-2 cursor-pointer group">
          <input type="checkbox" v-model="enrichWeb"
            class="w-4 h-4 rounded border-mist-depth bg-ocean-abyss text-ocean-cyan focus:ring-ocean-cyan/30 accent-ocean-cyan">
          <span class="text-sm text-mist-drift group-hover:text-mist-foam transition-colors">Enrich with web research</span>
        </label>
        <p class="text-xs text-mist-slate">Automatically research your topic using web and social media search</p>
      </div>
```

Key change: `<label>` now wraps only `<input>` and the title `<span>`. The description `<p>` is a sibling inside the parent `<div>`, so clicking it does nothing. Visual grouping is preserved by the parent flex container.

Then in `<script setup>`, add before the closing of the script block (this lets Vue Test Utils read `wrapper.vm.enrichWeb`):

```javascript
defineExpose({ enrichWeb })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- NewSimulation.enrichToggle`
Expected: 2 passed.

- [ ] **Step 5: Run full frontend test suite**

Run: `cd frontend && npm test -- --run`
Expected: no regressions.

- [ ] **Step 6: Visual sanity-check**

Run: `cd frontend && npm run dev`, open the wizard, confirm:
1. The description still appears beside the checkbox (not visually detached).
2. Clicking the description does nothing.
3. Clicking the checkbox or title toggles it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/NewSimulation.vue frontend/src/views/__tests__/NewSimulation.enrichToggle.test.js
git commit -m "fix(wizard): shrink enrich-web checkbox click target to title only"
```

---

### Task 8: Deduplicate deploy worker-image build

**Files:**
- Modify: `.github/workflows/deploy.yml`

The standalone `build-worker.yml` already builds and pushes `ghcr.io/.../worker:<sha>` on every `push: main`. Deploy currently does the same build in-line. We remove the in-line build and re-trigger deploy only when `Build Worker Image` completes successfully.

**Known caveat of `workflow_run`:** the triggering workflow must exist on the default branch. A deploy.yml edit in a feature branch won't take effect until it lands on `main`. Acceptable for a deploy-only workflow.

- [ ] **Step 1: Modify `.github/workflows/deploy.yml`**

Rewrite the whole file:

```yaml
name: Deploy to Hetzner

on:
  workflow_run:
    workflows: ["Build Worker Image"]
    types: [completed]
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository_owner }}/simswarm-worker

jobs:
  deploy:
    # Skip when the upstream build failed. workflow_dispatch runs don't
    # carry a workflow_run event, so the == 'success' check collapses to
    # false for manual runs — we fall back to always() so manual deploys
    # still work.
    if: |
      github.event_name == 'workflow_dispatch' ||
      github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
          # For workflow_run triggers, check out the commit that was built
          # (not the default branch HEAD, which may have advanced).
          ref: ${{ github.event.workflow_run.head_sha || github.sha }}

      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.3
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          command_timeout: 10m
          envs: ANTHROPIC_API_KEY
          script: |
            set -euo pipefail
            cd /opt/fishcloud
            git config --global --add safe.directory /opt/fishcloud
            git pull origin main
            git submodule update --recursive

            # Set worker image tag to current git commit
            SHORT_SHA=$(git rev-parse --short HEAD)
            if grep -q '^WORKER_IMAGE_TAG=' .env; then
                sed -i "s/^WORKER_IMAGE_TAG=.*/WORKER_IMAGE_TAG=${SHORT_SHA}/" .env
            else
                echo "WORKER_IMAGE_TAG=${SHORT_SHA}" >> .env
            fi

            # Sync ANTHROPIC_API_KEY from GitHub Secrets (used by the external
            # report-generation Celery task). Using grep+append instead of sed
            # to avoid delimiter issues with arbitrary key characters.
            if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
                grep -v '^ANTHROPIC_API_KEY=' .env > .env.tmp || true
                echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> .env.tmp
                mv .env.tmp .env
                chmod 600 .env
            fi

            # Build single image — celery/migrate/frontend-init all reuse it
            docker compose build --no-cache app

            # Pre-flight: verify app imports cleanly (catches broken imports before deploy)
            echo "Checking app imports..."
            docker compose run --rm --no-deps app python -c "from saas.main import create_app; print('Import check passed')"

            # Pre-flight: verify single migration head
            heads=$(docker compose run --rm --no-deps app alembic heads 2>/dev/null | grep -c head || true)
            if [ "$heads" -gt 1 ]; then
                echo "ERROR: Multiple alembic heads. Aborting deploy."
                docker compose run --rm --no-deps app alembic heads
                exit 1
            fi

            # Graceful Celery shutdown (finish in-flight tasks, 120s timeout)
            docker compose stop -t 120 celery || true

            # Run migrations
            docker compose run --rm migrate

            # Copy frontend assets into Caddy volume
            docker compose rm -f frontend-init || true
            docker compose run --rm frontend-init

            # Start services + restart Caddy to pick up new frontend assets
            docker compose up -d app celery redis db caddy
            docker compose restart caddy

            # Health check (wait up to 60s)
            for i in $(seq 1 20); do
                if curl -sf http://localhost:8080/api/health > /dev/null 2>&1; then
                    echo "Health check passed"
                    break
                fi
                if [ "$i" -eq 20 ]; then
                    echo "ERROR: Health check failed after 60s"
                    docker compose logs --tail=20 app
                    exit 1
                fi
                sleep 3
            done

            docker image prune -f
```

Changes vs current:
- Removed the `build-worker` job entirely (~44 lines).
- Removed `needs: build-worker` from the `deploy` job.
- Changed `on:` from `push: branches: [main]` to `workflow_run: { workflows: ["Build Worker Image"], types: [completed], branches: [main] }`.
- Added the conclusion-check `if:` guard at the deploy-job level.
- Added `ref: ${{ github.event.workflow_run.head_sha || github.sha }}` to the checkout step so workflow_run-triggered deploys check out the built commit.

- [ ] **Step 2: Lint the YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"`
Expected: no error. (We don't have `actionlint` available, but YAML parseability is the bar.)

- [ ] **Step 3: Commit on the feature branch, push**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: trigger deploy via workflow_run, drop duplicate build step"
git push -u origin fix/wizard-and-ci-cleanup
```

- [ ] **Step 4: Open PR 2**

```bash
gh pr create --title "Wizard checkbox scope + deploy worker-image dedup" --body "$(cat <<'EOF'
## Summary

Two small independent fixes.

- **Wizard enrich-web toggle surface** — the `<label>` now wraps only the input and the title span. Broad agent-browser text clicks on the description no longer flip the checkbox silently.
- **CI deploy dedup** — `deploy.yml` no longer rebuilds the worker image. It triggers via `workflow_run` on `Build Worker Image` success, reusing the tags that workflow already pushes. Manual deploys via `workflow_dispatch` still work via the `always()`-equivalent guard.

Known caveat: `workflow_run` triggers read the workflow from the default branch, so this PR's changes will only take effect once merged to `main`. The fallback for the first post-merge run is: push triggers `Build Worker Image` as before, which on success triggers the new deploy flow.

Spec: `docs/superpowers/specs/2026-04-14-post-miroshark-cleanup-design.md`.

## Test plan

- [x] `cd frontend && npm test -- NewSimulation.enrichToggle` (2 passed)
- [x] `cd frontend && npm test -- --run` (no regressions)
- [x] Manual visual check of wizard step 1 — description still beside checkbox, description click does nothing, title click toggles.
- [x] `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"` (parses)
- [ ] Post-merge: confirm exactly one `Build Worker Image` run per push to `main`, and a `Deploy to Hetzner` run chains off it only on success.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Record the PR URL**

---

## Post-Merge Verification (both PRs)

- [ ] Run one small sim end-to-end on prod. Confirm:
  - Agents tab shows 2–3 sentence personas (not "N posts, M actions…").
  - Graph canvas renders agent nodes in color, not uniform gray.
  - Top posts list shows `num_dislikes` where `vote -1` actions exist.
- [ ] Check Actions tab on GitHub: exactly one `Build Worker Image` per push, and `Deploy to Hetzner` triggers only after it succeeds.
- [ ] Click around wizard step 1 — confirm description-click does nothing, checkbox still toggles via checkbox-click and title-click.

---

## Self-Review Notes

- **Spec coverage:** goals 1–5 each map to tasks (1+2 → sentiment; 3 → dislikes; 4+5 → personas; 7 → checkbox; 8 → deploy dedup). Deferred items tracked in SimSwarm#70 / #71.
- **Placeholders:** none — all code, prompts, tests, and YAML blocks are complete.
- **Type consistency:** `agent_sentiment_from_trajectories`, `extract_personas`, `enrich_profiles_with_personas`, `PersonaExtractionError` all used with consistent signatures between definition and test call sites. Persona dict shape (`agent_id → str`) is consistent across module, tests, and runner wiring.
- **Scope:** two-PR split is intentional; each PR lands cleanly on its own, and the two concerns (backend extractors vs. frontend/CI) have zero shared files.
