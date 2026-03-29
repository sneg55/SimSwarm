# Graph Entity Sentiment Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-entity sentiment scores (-1.0 to +1.0) to graph nodes, derived from keyword-based analysis of chat_log content mentioning each entity.

**Architecture:** New `score_entity_sentiment()` function in run_job.py uses a positive/negative keyword lexicon to score entities by scanning chat_log content for mentions. Mutates graph_data nodes in place. GraphNode schema gains a `sentiment` field. Frontend already renders sentiment — no frontend changes needed.

**Tech Stack:** Python (run_job.py), Pydantic (graph schema)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `infra/docker/run_job.py` | Modify | Add `POSITIVE_WORDS`, `NEGATIVE_WORDS`, `score_entity_sentiment()` |
| `saas/schemas/graph.py` | Modify | Add `sentiment: float = 0.0` to GraphNode |
| `tests/test_entity_sentiment.py` | Create | Unit tests for scoring function |

---

### Task 1: Sentiment Scoring Function + Tests

**Files:**
- Modify: `infra/docker/run_job.py`
- Create: `tests/test_entity_sentiment.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_entity_sentiment.py
"""Tests for per-entity sentiment scoring from chat_log content."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

_INFRA_DOCKER = str(Path(__file__).parent.parent / "infra" / "docker")


def _import_run_job():
    """Import run_job with mocked MiroFish dependencies."""
    mock_modules = {
        "app": MagicMock(), "app.services": MagicMock(),
        "app.services.zep_tools": MagicMock(),
        "app.services.ontology_generator": MagicMock(),
        "app.services.graph_builder": MagicMock(),
        "app.services.text_processor": MagicMock(),
        "app.services.simulation_manager": MagicMock(),
        "app.services.simulation_runner": MagicMock(),
        "app.services.report_agent": MagicMock(),
        "app.config": MagicMock(),
    }
    with patch.dict(sys.modules, mock_modules):
        if _INFRA_DOCKER not in sys.path:
            sys.path.insert(0, _INFRA_DOCKER)
        if "run_job" in sys.modules:
            del sys.modules["run_job"]
        import run_job
        return run_job


def test_positive_mentions_score_positive():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "Apple", "labels": ["Company"], "summary": "", "connection_count": 1}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Company"]},
    }
    chat_log = [
        {"agent_name": "Analyst", "action_type": "CREATE_POST", "action_args": {"content": "Apple shows strong growth and success in the market. Investors praise the company."}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    assert graph_data["nodes"][0]["sentiment"] > 0


def test_negative_mentions_score_negative():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "Iran", "labels": ["Country"], "summary": "", "connection_count": 1}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Country"]},
    }
    chat_log = [
        {"agent_name": "Reporter", "action_type": "CREATE_POST", "action_args": {"content": "Iran threatens to escalate the conflict. The crisis deepens as attacks continue."}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    assert graph_data["nodes"][0]["sentiment"] < 0


def test_no_mentions_score_zero():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "Obscure Entity", "labels": ["Entity"], "summary": "", "connection_count": 0}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Entity"]},
    }
    chat_log = [
        {"agent_name": "Agent1", "action_type": "CREATE_POST", "action_args": {"content": "Something unrelated happening today."}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    assert graph_data["nodes"][0]["sentiment"] == 0.0


def test_mixed_mentions_score_between():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "Trump", "labels": ["Person"], "summary": "", "connection_count": 3}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Person"]},
    }
    chat_log = [
        {"agent_name": "Supporter", "action_type": "CREATE_POST", "action_args": {"content": "Trump shows strong leadership and progress on diplomacy."}},
        {"agent_name": "Critic", "action_type": "CREATE_POST", "action_args": {"content": "Trump threatens allies and escalates the crisis recklessly."}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    s = graph_data["nodes"][0]["sentiment"]
    assert -1.0 <= s <= 1.0


def test_agent_as_entity_scores():
    """Agent whose name matches an entity gets scored by their own posts."""
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "Meta", "labels": ["Company"], "summary": "", "connection_count": 1}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Company"]},
    }
    chat_log = [
        {"agent_name": "Meta", "action_type": "CREATE_POST", "action_args": {"content": "We oppose this dangerous ban that threatens innovation."}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    # "oppose", "dangerous", "threatens" are negative; "innovation" is neutral
    assert graph_data["nodes"][0]["sentiment"] < 0


def test_sentiment_clamped_to_range():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "TestCo", "labels": [], "summary": "", "connection_count": 0}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": []},
    }
    chat_log = [
        {"agent_name": "X", "action_type": "CREATE_POST", "action_args": {"content": "TestCo fail fail fail fail fail crisis crisis crisis"}},
    ]
    run_job.score_entity_sentiment(graph_data, chat_log)
    s = graph_data["nodes"][0]["sentiment"]
    assert s >= -1.0 and s <= 1.0


def test_empty_chat_log():
    run_job = _import_run_job()
    graph_data = {
        "nodes": [{"uuid": "n1", "name": "A", "labels": [], "summary": "", "connection_count": 0}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": []},
    }
    run_job.score_entity_sentiment(graph_data, [])
    assert graph_data["nodes"][0]["sentiment"] == 0.0


def test_empty_graph_nodes():
    run_job = _import_run_job()
    graph_data = {"nodes": [], "edges": [], "metadata": {"total_nodes": 0, "total_edges": 0, "entity_types": []}}
    run_job.score_entity_sentiment(graph_data, [{"agent_name": "X", "action_type": "CREATE_POST", "action_args": {"content": "test"}}])
    assert graph_data["nodes"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_entity_sentiment.py -v`
Expected: FAIL — `score_entity_sentiment` not defined

- [ ] **Step 3: Implement score_entity_sentiment in run_job.py**

Add after the `FINDING_COLORS` constant and before `build_structured_results()`:

```python
# ---------------------------------------------------------------------------
# Per-entity sentiment scoring (keyword lexicon, no LLM)
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "support", "approve", "praise", "welcome", "benefit", "success", "agree",
    "positive", "progress", "growth", "improve", "achieve", "gain", "boost",
    "encourage", "optimistic", "favorable", "advance", "strengthen", "celebrate",
    "endorse", "commend", "constructive", "prosper", "thrive", "cooperate",
    "alliance", "partnership", "diplomatic", "peaceful", "stable", "recovery",
    "innovation", "opportunity", "confident", "resolve", "protect", "invest",
    "expand", "lead", "unite", "embrace", "recommend", "affirm", "uphold",
    "champion", "reform", "empower", "sustain", "reliable",
}

NEGATIVE_WORDS = {
    "oppose", "condemn", "reject", "threaten", "crisis", "fail", "warn",
    "attack", "ban", "sanction", "conflict", "damage", "destroy", "collapse",
    "risk", "danger", "decline", "loss", "struggle", "tension", "hostile",
    "aggressive", "escalate", "violate", "disrupt", "undermine", "restrict",
    "protest", "controversy", "criticism", "backlash", "concern", "fear",
    "instability", "vulnerable", "deficit", "recession", "inflation", "corrupt",
    "exploit", "abuse", "negligence", "incompetent", "reckless", "toxic",
    "polarize", "divide", "obstruct", "retaliate", "assassinate",
}


def score_entity_sentiment(graph_data: dict, chat_log: list[dict]) -> None:
    """Score each graph node's sentiment by analyzing chat_log mentions.

    Mutates graph_data["nodes"] in place, adding a "sentiment" float field
    (-1.0 to +1.0) to each node.
    """
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return

    # Build lookup: lowercase entity name → node index(es)
    name_to_indices: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        name = node.get("name", "").strip()
        if name:
            name_to_indices.setdefault(name.lower(), []).append(i)

    # Accumulate sentiment scores per node index
    pos_counts: dict[int, int] = {}
    neg_counts: dict[int, int] = {}
    mention_counts: dict[int, int] = {}

    for entry in chat_log:
        content = (entry.get("action_args") or {}).get("content", "")
        if not content:
            continue
        content_lower = content.lower()
        agent_name = (entry.get("agent_name") or "").strip().lower()

        # Count positive/negative words in this entry
        words = set(content_lower.split())
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)

        # Find which entities are mentioned in this content
        matched_indices: set[int] = set()
        for entity_name, indices in name_to_indices.items():
            if entity_name in content_lower:
                matched_indices.update(indices)
            # Agent-as-entity: if agent_name matches entity
            if agent_name and agent_name == entity_name:
                matched_indices.update(indices)

        for idx in matched_indices:
            pos_counts[idx] = pos_counts.get(idx, 0) + pos
            neg_counts[idx] = neg_counts.get(idx, 0) + neg
            mention_counts[idx] = mention_counts.get(idx, 0) + 1

    # Compute sentiment score per node
    for i, node in enumerate(nodes):
        p = pos_counts.get(i, 0)
        n = neg_counts.get(i, 0)
        total = p + n
        if total == 0:
            node["sentiment"] = 0.0
        else:
            node["sentiment"] = round(max(-1.0, min(1.0, (p - n) / total)), 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_entity_sentiment.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add infra/docker/run_job.py tests/test_entity_sentiment.py
git commit -m "feat: per-entity sentiment scoring from chat_log keyword analysis (#25)"
```

---

### Task 2: Wire into Pipeline + Schema Update

**Files:**
- Modify: `infra/docker/run_job.py` (run_pipeline function)
- Modify: `saas/schemas/graph.py`

- [ ] **Step 1: Add sentiment field to GraphNode schema**

In `saas/schemas/graph.py`, update `GraphNode`:

```python
class GraphNode(BaseModel):
    uuid: str
    name: str
    labels: list[str] = []
    summary: str = ""
    connection_count: int = 0
    sentiment: float = 0.0
```

- [ ] **Step 2: Wire score_entity_sentiment into run_pipeline**

In `infra/docker/run_job.py`, in `run_pipeline()`, add after `graph_data = extract_graph_data(graph_id)` (line 514):

```python
    # Score per-entity sentiment from chat_log mentions
    try:
        score_entity_sentiment(graph_data, chat_log)
        scored = sum(1 for n in graph_data.get("nodes", []) if n.get("sentiment", 0) != 0)
        print(f"[run_job] Sentiment scored: {scored}/{len(graph_data.get('nodes', []))} entities with non-zero sentiment", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: sentiment scoring failed: {exc}", flush=True)
```

- [ ] **Step 3: Write integration test**

Append to `tests/test_entity_sentiment.py`:

```python
def test_graph_node_schema_has_sentiment():
    from saas.schemas.graph import GraphNode
    node = GraphNode(uuid="n1", name="Test", sentiment=0.5)
    assert node.sentiment == 0.5


def test_graph_node_schema_defaults_zero():
    from saas.schemas.graph import GraphNode
    node = GraphNode(uuid="n1", name="Test")
    assert node.sentiment == 0.0
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_entity_sentiment.py tests/test_graph_api.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add saas/schemas/graph.py infra/docker/run_job.py tests/test_entity_sentiment.py
git commit -m "feat: wire sentiment into pipeline, add sentiment to GraphNode schema (#25)"
```

---

### Task 3: Verify Full Suite + Lint

- [ ] **Step 1: Run all backend tests**

Run: `pytest tests/ --tb=short -q`
Expected: All pass

- [ ] **Step 2: Lint**

Run: `ruff check saas/ tests/`
Expected: Clean

- [ ] **Step 3: Build frontend** (no changes expected, just verify)

Run: `cd frontend && npm run build`
Expected: Builds without errors

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "fix: lint and test fixups for entity sentiment"
```
