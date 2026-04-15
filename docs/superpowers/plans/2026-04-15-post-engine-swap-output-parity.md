# Post-Engine-Swap Output Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore all simulation output surfaces (Executive Brief, Findings with full shape, ConfidenceGrid, Coalitions, Sentiment, graph stance/influence, chat replay text, live-status progress, export JSON) that regressed after the MiroShark → SimSwarm engine cutover.

**Architecture:** Ten independent but ordered fixes spanning the pod runner, the Celery report task, the pydantic contract, the Vue composables, and the FastAPI export endpoint. The core restoration uses the already-tested-but-orphaned `simswarm.adapter.adapt_structured` called from `tasks_report._build_structured` with chat_log + graph loaded from the DB row the sim task just wrote. Other fixes align the engine-side extractors, frontend composables, and worker progress emissions with what the frontend and pipeline contracts already expect.

**Tech Stack:** Python 3.11 (pytest + pytest-asyncio, SQLAlchemy async, Celery), Vue 3 (Vitest), PostgreSQL, MinIO.

---

## File Structure

Files touched by this plan, grouped by responsibility:

**Report structured output (Task 1, 6):**
- Modify: `saas/jobs/tasks_report.py` — rewrite `_build_structured`, add chat_log/graph loader
- Modify: `saas/jobs/persistence_sync.py` — expose `_load_job_artifacts` read helper
- Modify: `tests/jobs/test_tasks_report.py` — assert full structured shape
- Create: `tests/jobs/test_build_structured.py` — focused tests for the new helper

**Frontend chat rendering (Task 2):**
- Modify: `frontend/src/composables/useSimulationData.js`
- Modify: `frontend/src/composables/__tests__/useSimulationData.spec.js`

**Agent ID unification (Task 3):**
- Modify: `simswarm/adapter.py` — drop `hash()` in `adapt_chat_log`
- Modify: `tests/contracts/schemas.py` — `ChatLogEntry.agent_id: str`
- Modify: `tests/engine/test_adapter.py` — update int-hash expectations to string

**Graph node enrichment (Task 4, 5):**
- Modify: `simswarm/graph.py` — add `entity_types` to metadata
- Modify: `infra/docker/run_job_v2_runner.py` — stamp `stance`/`influence_weight` from `result.raw_state.agents`
- Modify: `tests/engine/test_graph.py` (create if missing) — cover metadata + stamping
- Modify: `tests/engine/test_run_job_v2_chat_log.py` — verify graph_data.json contains stance/influence_weight

**Empty structured guard (Task 7):**
- Modify: `frontend/src/composables/useSimulationData.js` — treat `{}` as null

**Pod progress emissions (Task 8):**
- Modify: `infra/docker/run_job_v2.py` — print stage markers
- Modify: `infra/docker/run_job_v2_runner.py` — pass `on_progress` callback that prints `round=N/M`
- Modify: `tests/engine/test_run_job_v2_stage_progress.py` (create) — assert markers in stdout

**Export JSON (Task 9):**
- Modify: `saas/jobs/export.py` — include structured, enriched_seed, enrichment_citations, key_insight
- Modify: `tests/test_export_endpoints.py` — assert new fields

**Demo fixtures (Task 10):**
- Modify: `infra/scripts/import_demos.py` — write new structured shape
- Modify: `tests/test_demos_import.py` (create if missing) — validate golden demo rows

---

## Task 1: Restore full `result_structured` via `adapt_structured`

**Files:**
- Modify: `saas/jobs/tasks_report.py:117-154`
- Modify: `saas/jobs/persistence_sync.py` (append `_load_job_artifacts` helper)
- Test: `tests/jobs/test_build_structured.py` (create)
- Test: `tests/jobs/test_tasks_report.py` (update happy-path assertion)

- [ ] **Step 1: Write failing test — `_build_structured` returns full shape**

Create `tests/jobs/test_build_structured.py`:

```python
"""Verify _build_structured produces the full 5-key shape via adapt_structured."""
from __future__ import annotations

import json
from unittest.mock import patch

from saas.jobs.report import ReportResult
from saas.jobs.tasks_report import _build_structured


def _fake_artifacts():
    chat_log = [
        {"round_num": 1, "agent_id": "a1", "agent_name": "Alice",
         "action_type": "CREATE_POST", "platform": "twitter",
         "action_args": {"text": "Hi"}, "success": True, "timestamp": None},
        {"round_num": 2, "agent_id": "a2", "agent_name": "Bob",
         "action_type": "BUY", "platform": "polymarket",
         "action_args": {"qty": 10}, "success": True, "timestamp": None},
    ]
    graph = {
        "nodes": [{"id": "a1", "uuid": "a1", "name": "Alice", "labels": ["Person"],
                   "summary": "", "connection_count": 0, "sentiment": 0.0}],
        "edges": [],
        "metadata": {"total_nodes": 1, "total_edges": 0, "entity_types": ["Person"]},
    }
    return json.dumps(chat_log), json.dumps(graph)


def test_build_structured_emits_all_five_keys():
    chat_json, graph_json = _fake_artifacts()
    result = ReportResult(
        report_markdown="## Executive Summary\nSomething.\n## Key Findings\n### Finding 1: X\nBody.",
        executive_brief="Something.",
        findings=[{"title": "Finding 1: X", "content": "Body."}],
    )
    with patch("saas.jobs.tasks_report._load_job_artifacts",
               return_value=(chat_json, graph_json)):
        out = json.loads(_build_structured(job_id=42, result=result))
    assert set(out.keys()) == {"brief", "findings", "confidence", "coalitions", "sentiment"}
    assert out["brief"] == "Something."
    assert any(c["label"] == "Agents" for c in out["confidence"])
    assert all({"label", "title", "description", "metric", "accentColor"} <= set(f)
               for f in out["findings"])


def test_build_structured_empty_artifacts_still_valid():
    with patch("saas.jobs.tasks_report._load_job_artifacts",
               return_value=("[]", '{"nodes": [], "edges": [], "metadata": {}}')):
        out = json.loads(_build_structured(
            job_id=1,
            result=ReportResult(report_markdown="", executive_brief="", findings=[]),
        ))
    assert out["brief"] == ""
    assert out["findings"] == []
    assert isinstance(out["confidence"], list)
    assert isinstance(out["coalitions"], list)
    assert isinstance(out["sentiment"], list)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/jobs/test_build_structured.py -v`
Expected: FAIL — `_build_structured` takes a single `result` arg (not `job_id`) and `_load_job_artifacts` does not exist.

- [ ] **Step 3: Add `_load_job_artifacts` helper to `persistence_sync.py`**

Append to `saas/jobs/persistence_sync.py`:

```python
def _load_job_artifacts(job_id: int) -> tuple[str, str]:
    """Return (result_chat_log, result_graph) JSON strings for *job_id*.

    Used by the report task to hand already-persisted sim artifacts to
    simswarm.adapter.adapt_structured without re-fetching from MinIO.
    """
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        return "[]", "{}"
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT result_chat_log, result_graph "
                    "FROM simulation_jobs WHERE id = :id"
                ),
                {"id": job_id},
            ).first()
            if not row:
                return "[]", "{}"
            return (row[0] or "[]", row[1] or "{}")
    finally:
        engine.dispose()
```

- [ ] **Step 4: Rewrite `_build_structured` in `tasks_report.py`**

Replace the body of `saas/jobs/tasks_report.py:147-154` and update the call at line 117:

```python
# at imports:
from saas.jobs.persistence_sync import _load_job_artifacts
from simswarm.adapter import adapt_structured

# replace the existing _build_structured:
def _build_structured(job_id: int, result) -> str:
    """Produce the full structured_results JSON string consumed by the Vue
    SimulationResults Story view. Loads the chat log + graph the sim task
    already wrote to the DB, then delegates to simswarm.adapter.adapt_structured
    so `brief`, correctly-shaped `findings`, `confidence`, `coalitions`,
    and `sentiment` are all present."""
    import json as _json

    chat_log_json, graph_json = _load_job_artifacts(job_id)
    try:
        chat_log = _json.loads(chat_log_json) if chat_log_json else []
    except _json.JSONDecodeError:
        chat_log = []
    try:
        graph_data = _json.loads(graph_json) if graph_json else {}
    except _json.JSONDecodeError:
        graph_data = {}

    structured_dict = adapt_structured(
        brief=result.executive_brief,
        findings=result.findings,
        chat_log=chat_log,
        graph_data=graph_data,
    )
    return _json.dumps(structured_dict)
```

And update the call site `saas/jobs/tasks_report.py:117`:

```python
    structured = _build_structured(job_id=job_id, result=result)
```

- [ ] **Step 5: Update `tests/jobs/test_tasks_report.py` to expect new signature**

Modify the happy-path test (`test_happy_path_persists_and_marks_completed`) to mock `_load_job_artifacts`:

```python
@pytest.mark.asyncio
async def test_happy_path_persists_and_marks_completed():
    from saas.jobs.report import ReportResult

    result = ReportResult(
        report_markdown="## Executive Summary\nAll went well.\n",
        executive_brief="All went well.",
        findings=[{"title": "F1", "content": "X"}],
    )

    with patch("saas.jobs.tasks_report._build_runner", return_value=_DummyRunner(result=result)), \
         patch("saas.jobs.tasks_report._load_job_artifacts", return_value=("[]", "{}")), \
         patch("saas.jobs.tasks_report._save_report_result") as save, \
         patch("saas.jobs.tasks_report.put_report_md") as putmd, \
         patch("saas.jobs.tasks_report._load_credits_charged", return_value=30):
        out = generate_report_task.run(job_id=123, user_id="u1")

    assert out["status"] == "completed"
    save.assert_called_once()
    # structured must contain the 5-key shape now
    saved_structured = save.call_args.kwargs["structured"]
    import json as _json
    parsed = _json.loads(saved_structured)
    assert {"brief", "findings", "confidence", "coalitions", "sentiment"} <= set(parsed.keys())
    putmd.assert_called_once_with(123, result.report_markdown)
```

- [ ] **Step 6: Run both tests to verify they pass**

Run: `pytest tests/jobs/test_build_structured.py tests/jobs/test_tasks_report.py -v`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add saas/jobs/tasks_report.py saas/jobs/persistence_sync.py tests/jobs/test_build_structured.py tests/jobs/test_tasks_report.py
git commit -m "fix(jobs): restore full structured report payload via adapt_structured"
```

---

## Task 2: Chat replay reads `action_args.text` for post content

**Files:**
- Modify: `frontend/src/composables/useSimulationData.js:13-25`
- Test: `frontend/src/composables/__tests__/useSimulationData.spec.js`

- [ ] **Step 1: Write failing test — post body read from `action_args.text`**

Append to `frontend/src/composables/__tests__/useSimulationData.spec.js` (inside the existing `describe` block):

```javascript
  it('reads post body from action_args.text (native engine key)', () => {
    const job = ref({ result_chat_log: JSON.stringify([
      { agent_name: 'Alice', action_type: 'CREATE_POST', action_args: { text: 'hello world' } },
    ]) })
    const { chatMessages } = useSimulationData(job)
    expect(chatMessages.value[0].content).toBe('hello world')
  })

  it('prefers action_args.text over action_args.content when both present', () => {
    const job = ref({ result_chat_log: JSON.stringify([
      { agent_name: 'Alice', action_type: 'CREATE_POST',
        action_args: { text: 'from text', content: 'from content' } },
    ]) })
    const { chatMessages } = useSimulationData(job)
    expect(chatMessages.value[0].content).toBe('from text')
  })
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- useSimulationData`
Expected: 2 new tests FAIL — `content` is `"{"text":"hello world"}"` (stringified args).

- [ ] **Step 3: Fix the `content` resolution order**

In `frontend/src/composables/useSimulationData.js`, replace lines 13-25:

```javascript
  const chatMessages = computed(() => {
    return chatLog.value
      .map(entry => {
        if (entry.content && entry.role) return entry
        const args = entry.action_args || {}
        const body = args.text ?? args.content ?? entry.content
        return {
          role: 'assistant',
          agent: entry.agent_name || entry.agent || 'Agent',
          content: body ?? JSON.stringify(args),
          timestamp: entry.timestamp || null,
        }
      })
      .filter(m => m.content)
  })
```

- [ ] **Step 4: Run tests to verify they pass (and existing tests still pass)**

Run: `cd frontend && npm test -- useSimulationData`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimulationData.js frontend/src/composables/__tests__/useSimulationData.spec.js
git commit -m "fix(frontend): read post body from action_args.text in chat replay"
```

---

## Task 3: Unify `agent_id` as string across chat_log + extractors

**Files:**
- Modify: `simswarm/adapter.py:26-44`
- Modify: `tests/contracts/schemas.py:12-21`
- Modify: `tests/engine/test_adapter.py` (tests asserting int-hash behavior)
- Modify: `tests/engine/adapter_fixtures.py` (if needed)

- [ ] **Step 1: Update the contract — `agent_id` is `str`**

In `tests/contracts/schemas.py`, change `ChatLogEntry`:

```python
class ChatLogEntry(BaseModel):
    round_num: int
    agent_id: str
    agent_name: str
    action_type: str
    platform: str
    action_args: dict
    timestamp: str | None = None
    result: str | None = None
    success: bool | None = None
```

- [ ] **Step 2: Write failing test — adapt_chat_log keeps agent_id as string**

Replace the `test_agent_id_converted_to_int` / `test_agent_id_hash_formula` / `test_same_agent_id_str_maps_to_same_int` / `test_different_agent_ids_map_to_different_ints` tests in `tests/engine/test_adapter.py` with:

```python
    def test_agent_id_preserved_as_string(self):
        for entry in adapt_chat_log(make_records()):
            assert isinstance(entry["agent_id"], str)

    def test_agent_id_value_matches_record(self):
        record_ids = [r.agent_id for r in make_records()]
        adapted_ids = [e["agent_id"] for e in adapt_chat_log(make_records())]
        assert adapted_ids == record_ids
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/engine/test_adapter.py -v`
Expected: new tests FAIL — adapter still emits hashed ints.

- [ ] **Step 4: Drop the hash in `adapt_chat_log`**

In `simswarm/adapter.py`, replace lines 26-44:

```python
def adapt_chat_log(chat_log: list[ActionRecord]) -> list[dict]:
    """Convert ActionRecords to dicts consumed by the SaaS frontend.

    agent_id is preserved as a string. (The old MiroShark-compat hashing was
    dropped after the engine cutover — extractors keep string agent_ids and
    the frontend never required int typing.)
    """
    result = []
    for record in chat_log:
        result.append({
            "round_num": record.round_num,
            "agent_id": record.agent_id,
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "platform": record.platform,
            "action_args": record.action_args,
            "timestamp": record.timestamp,
            "success": record.success,
        })
    return result
```

- [ ] **Step 5: Run all engine tests to verify they pass**

Run: `pytest tests/engine/ tests/contracts/ -v`
Expected: all PASS. If any test references integer agent_ids, update its fixture to use strings.

- [ ] **Step 6: Commit**

```bash
git add simswarm/adapter.py tests/contracts/schemas.py tests/engine/test_adapter.py
git commit -m "refactor(adapter): keep agent_id as string after miroshark removal"
```

---

## Task 4: Stamp `stance` and `influence_weight` onto graph nodes

**Files:**
- Modify: `infra/docker/run_job_v2_runner.py:257-283`
- Test: `tests/engine/test_run_job_v2_chat_log.py` (or nearest fixture; add new test class)

- [ ] **Step 1: Write failing test — graph_data.json nodes carry stance + influence_weight**

Append a new test to `tests/engine/test_run_job_v2_chat_log.py`:

```python
class TestGraphNodeAgentAttrs:
    def test_nodes_carry_stance_and_influence_weight(self, rjv2, tmp_path):  # noqa: F811
        """write_results must stamp AgentActivityConfig.stance and
        influence_weight onto graph nodes so the Graph detail panel can
        render them."""
        import json
        from simswarm.types import (
            Agent, AgentActivityConfig, BeliefState, SimulationState,
        )

        result = make_simulation_result()
        # Populate raw_state.agents with two agents that match the graph node ids
        ag1 = Agent(
            id="n1", name="Alice", persona="", environments=[],
            belief_state=BeliefState(),
            config=AgentActivityConfig(stance="supportive", influence_weight=1.5),
        )
        ag2 = Agent(
            id="n2", name="Bob", persona="", environments=[],
            belief_state=BeliefState(),
            config=AgentActivityConfig(stance="opposing", influence_weight=0.8),
        )
        result.raw_state = SimulationState(
            round=1, agents={"n1": ag1, "n2": ag2},
            environments={}, events=[], snapshots=[],
        )
        rjv2.write_results(result, str(tmp_path))

        data = json.loads((tmp_path / "graph_data.json").read_text(encoding="utf-8"))
        by_id = {n["id"]: n for n in data["nodes"]}
        assert by_id["n1"]["stance"] == "supportive"
        assert by_id["n1"]["influence_weight"] == 1.5
        assert by_id["n2"]["stance"] == "opposing"
        assert by_id["n2"]["influence_weight"] == 0.8
```

(Ensure `make_simulation_result` returns a result whose graph_data has nodes with ids `n1`/`n2`; if it doesn't, extend the fixture or override ids inline.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/engine/test_run_job_v2_chat_log.py::TestGraphNodeAgentAttrs -v`
Expected: FAIL — nodes have no `stance` / `influence_weight` keys.

- [ ] **Step 3: Stamp stance/influence_weight in write_results**

In `infra/docker/run_job_v2_runner.py`, insert after line 269 (after the sentiment stamping block):

```python
    # Stamp per-agent stance + influence_weight from the live SimulationState
    # onto graph nodes so the frontend detail panel can render them.
    stance_by_agent: dict[str, str] = {}
    weight_by_agent: dict[str, float] = {}
    raw_state = getattr(result, "raw_state", None)
    if raw_state is not None:
        for aid, agent in raw_state.agents.items():
            cfg = getattr(agent, "config", None)
            if cfg is None:
                continue
            stance_by_agent[aid] = cfg.stance
            weight_by_agent[aid] = cfg.influence_weight
    for node in adapted_graph.get("nodes", []):
        nid = node.get("id")
        if nid in stance_by_agent:
            node["stance"] = stance_by_agent[nid]
        if nid in weight_by_agent:
            node["influence_weight"] = weight_by_agent[nid]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/engine/test_run_job_v2_chat_log.py::TestGraphNodeAgentAttrs -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add infra/docker/run_job_v2_runner.py tests/engine/test_run_job_v2_chat_log.py
git commit -m "fix(graph): stamp per-agent stance and influence_weight on graph nodes"
```

---

## Task 5: Populate `entity_types` in graph metadata

**Files:**
- Modify: `simswarm/graph.py:43-67`
- Test: `tests/engine/test_graph.py` (create if missing, else append)

- [ ] **Step 1: Write failing test**

Create `tests/engine/test_graph.py` (or append if it already exists):

```python
"""Tests for simswarm.graph.build_graph metadata."""
from __future__ import annotations

from simswarm.graph import build_graph
from simswarm.types import Entity


def _ents():
    return [
        Entity(id="a1", name="Alice", type="Person", summary=""),
        Entity(id="o1", name="OpenAI", type="Organization", summary=""),
        Entity(id="a2", name="Bob", type="Person", summary=""),
    ]


def test_metadata_entity_types_is_unique_sorted():
    g = build_graph(_ents(), chat_log=[])
    assert g.metadata["entity_types"] == ["Organization", "Person"]


def test_metadata_entity_types_empty_for_no_entities():
    g = build_graph([], chat_log=[])
    assert g.metadata["entity_types"] == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/engine/test_graph.py -v`
Expected: FAIL — metadata does not contain `entity_types`.

- [ ] **Step 3: Emit `entity_types` in `build_graph`**

In `simswarm/graph.py`, update the `metadata` block in `build_graph` (lines 62-66):

```python
    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_rounds": max((a.round_num for a in chat_log), default=0),
        "entity_types": sorted({e.type for e in entities}),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/engine/test_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add simswarm/graph.py tests/engine/test_graph.py
git commit -m "feat(graph): populate entity_types in GraphSnapshot metadata"
```

---

## Task 6: Guardrail test — report markdown contains all 5 required sections

**Files:**
- Test: `tests/jobs/test_report_sections.py` (create)

- [ ] **Step 1: Write test pinning the 5 required sections**

Create `tests/jobs/test_report_sections.py`:

```python
"""Prevent silent regressions where the report prompt drops a section.

The SimulationResults Story view + SharedResult expect five sections in
the LLM-generated markdown. This test asserts the prompt template lists
all five explicitly."""
from __future__ import annotations

from pathlib import Path


REPORT_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "simswarm" / "prompts" / "report.j2"
)


def test_report_prompt_lists_all_five_sections():
    text = REPORT_TEMPLATE.read_text(encoding="utf-8")
    for heading in (
        "## Executive Summary",
        "## Key Findings",
        "## Agent Coalitions",
        "## Market Analysis",
        "## Conclusion",
    ):
        assert heading in text, f"Report prompt missing {heading!r}"
```

- [ ] **Step 2: Run the test to verify it passes (it should — this is a guardrail)**

Run: `pytest tests/jobs/test_report_sections.py -v`
Expected: PASS (report.j2 already has all five).

- [ ] **Step 3: Commit**

```bash
git add tests/jobs/test_report_sections.py
git commit -m "test(jobs): pin report prompt to 5 required sections"
```

---

## Task 7: Frontend — treat empty `structured` object as null

**Files:**
- Modify: `frontend/src/composables/useSimulationData.js:27-33`
- Test: `frontend/src/composables/__tests__/useSimulationData.spec.js`

- [ ] **Step 1: Write failing test — empty-dict structured becomes null**

Append to `frontend/src/composables/__tests__/useSimulationData.spec.js`:

```javascript
  it('returns null for empty-object structured (REPORTING window)', () => {
    const job = ref({ result_structured: '{}' })
    const { structured } = useSimulationData(job)
    expect(structured.value).toBe(null)
  })

  it('returns object for non-empty structured', () => {
    const job = ref({ result_structured: JSON.stringify({ brief: 'x' }) })
    const { structured } = useSimulationData(job)
    expect(structured.value).toEqual({ brief: 'x' })
  })
```

- [ ] **Step 2: Run tests to verify the empty-dict test fails**

Run: `cd frontend && npm test -- useSimulationData`
Expected: empty-dict test FAILS (currently returns `{}`).

- [ ] **Step 3: Update the `structured` computed**

In `frontend/src/composables/useSimulationData.js`, replace lines 27-33:

```javascript
  const structured = computed(() => {
    const raw = job.value?.result_structured ?? job.value?.structured ?? null
    if (!raw) return null
    try {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          && Object.keys(parsed).length === 0) {
        return null
      }
      return parsed
    } catch { return null }
  })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- useSimulationData`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimulationData.js frontend/src/composables/__tests__/useSimulationData.spec.js
git commit -m "fix(frontend): treat empty structured object as null during REPORTING"
```

---

## Task 8: Pod emits progress markers for stage inference + live round counter

**Files:**
- Modify: `infra/docker/run_job_v2.py:51-74`
- Modify: `infra/docker/run_job_v2_runner.py:155-184` (add `on_progress` param + callback)
- Test: `tests/engine/test_run_job_v2_stage_progress.py` (create)

`saas/jobs/status.py::_infer_pipeline_stage` and `_extract_live_status` need the pod to print four keyword markers. Each marker is a simple line; `run_simulation` forwards a per-round progress callback to the engine (which already exposes `on_progress`).

- [ ] **Step 1: Write failing test**

Create `tests/engine/test_run_job_v2_stage_progress.py`:

```python
"""The pod must emit stage markers and `round=N/M` lines so the Celery
pipeline can infer pipeline_stage and update live_status.round."""
from __future__ import annotations

from unittest.mock import patch


def test_run_pipeline_emits_stage_markers(capsys, tmp_path):
    """run_pipeline prints the four stage markers status.py expects."""
    from infra.docker import run_job_v2

    from simswarm.types import GraphSnapshot, SimulationResult, SimulationState

    # Stub run_simulation so we don't need GPUs / LLMs.
    def _fake_run_simulation(seed_text, goal, max_rounds, entities, target_agents):
        return SimulationResult(
            chat_log=[],
            graph_data=GraphSnapshot(
                nodes=[], edges=[],
                metadata={"total_nodes": 0, "total_edges": 0, "entity_types": []},
            ),
            trajectories={},
            raw_state=SimulationState(
                round=max_rounds, agents={}, environments={}, events=[], snapshots=[],
            ),
        )

    with patch("infra.docker.run_job_v2.get_entities", return_value=[]), \
         patch("infra.docker.run_job_v2.run_simulation", side_effect=lambda *a, **kw: _fake_run_simulation(*a, **kw)):
        run_job_v2.run_pipeline(
            seed_text="x", goal="g", max_rounds=3,
            output_dir=str(tmp_path), target_agents=2,
        )

    captured = capsys.readouterr().out
    assert "Generating ontology" in captured
    assert "Building" in captured
    assert "Running simulation" in captured


def test_run_simulation_emits_round_markers(capsys):
    """Every completed round must print `round=N/M` for live_status parsing."""
    import asyncio
    from types import SimpleNamespace

    from infra.docker import run_job_v2_runner

    captured_progress = []

    class _FakeEngine:
        def __init__(self, *a, **kw):
            pass

        async def run(self, config, on_progress=None):
            if on_progress:
                for r in range(1, config.rounds + 1):
                    await on_progress(r, config.rounds, {})
                    captured_progress.append(r)
            from simswarm.types import GraphSnapshot, SimulationResult
            return SimulationResult(
                chat_log=[],
                graph_data=GraphSnapshot(nodes=[], edges=[], metadata={}),
                trajectories={},
            )

    with patch("infra.docker.run_job_v2_runner.Engine", _FakeEngine), \
         patch("infra.docker.run_job_v2_runner.LLMClient", lambda **kw: SimpleNamespace(close=lambda: None)), \
         patch("infra.docker.run_job_v2_runner.extract_relations", side_effect=lambda *a, **kw: []), \
         patch("infra.docker.run_job_v2_runner.enrich_profiles_with_personas", side_effect=lambda profiles, *a, **kw: profiles):
        asyncio.run(run_job_v2_runner.run_simulation(
            seed_text="x", goal="g", max_rounds=3, entities=[], target_agents=1,
        ))

    out = capsys.readouterr().out
    assert "round=1/3" in out
    assert "round=2/3" in out
    assert "round=3/3" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_run_job_v2_stage_progress.py -v`
Expected: FAIL — markers not emitted.

- [ ] **Step 3: Add stage markers in `run_pipeline`**

In `infra/docker/run_job_v2.py`, replace `run_pipeline` (lines 51-74):

```python
def run_pipeline(
    seed_text: str,
    goal: str,
    max_rounds: int,
    output_dir: str,
    target_agents: int = 5,
) -> dict:
    """Sim-only pipeline: entities → simulation → write non-report artifacts.

    Stage markers below match the keywords saas/jobs/status.py scans for.
    """
    print("[stage] Generating ontology", flush=True)
    entities = get_entities(seed_text, goal, target_agents)

    print("[stage] Building entity graph", flush=True)

    print("[stage] Running simulation", flush=True)
    result = asyncio.run(
        run_simulation(seed_text, goal, max_rounds, entities, target_agents)
    )
    print(
        f"[run_job_v2] Simulation complete: {len(result.chat_log)} actions",
        flush=True,
    )

    print("[stage] preparing sim data artifacts", flush=True)
    write_results(result, output_dir)

    out = Path(output_dir)
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))
```

- [ ] **Step 4: Wire the round-progress callback in `run_simulation`**

In `infra/docker/run_job_v2_runner.py`, update `run_simulation` (replace the `engine.run(config)` call):

```python
    async def _on_progress(round_num: int, total: int, _metrics: dict) -> None:
        print(f"round={round_num}/{total}", flush=True)

    try:
        result = await engine.run(config, on_progress=_on_progress)
```

(Leave the rest of the function body unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/engine/test_run_job_v2_stage_progress.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add infra/docker/run_job_v2.py infra/docker/run_job_v2_runner.py tests/engine/test_run_job_v2_stage_progress.py
git commit -m "fix(pod): emit stage markers and per-round progress for live_status"
```

---

## Task 9: Extend `/jobs/{id}/export/json` with structured + enrichment + insight

**Files:**
- Modify: `saas/jobs/export.py:38-67`
- Test: `tests/test_export_endpoints.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_export_endpoints.py` (inside the existing test class or as a new function; match style of adjacent tests):

```python
@pytest.mark.asyncio
async def test_export_json_includes_structured_and_enrichment(client, funded_user, db_session):
    from saas.jobs.models import SimulationJob, JobStatus
    import json

    job = SimulationJob(
        user_id=funded_user["user_id"],
        seed_text="s", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Done", result_chat_log="[]", result_graph="{}",
        result_structured='{"brief": "b", "findings": []}',
        enriched_seed="background facts",
        enrichment_citations='[{"url": "https://x.test", "title": "Src"}]',
        key_insight="headline finding",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/jobs/{job.id}/export/json", headers=funded_user["headers"])
    assert resp.status_code == 200
    body = json.loads(resp.content)
    assert body["structured"] == {"brief": "b", "findings": []}
    assert body["enriched_seed"] == "background facts"
    assert body["enrichment_citations"] == [{"url": "https://x.test", "title": "Src"}]
    assert body["key_insight"] == "headline finding"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_export_endpoints.py::test_export_json_includes_structured_and_enrichment -v`
Expected: FAIL — keys missing.

- [ ] **Step 3: Extend the export**

In `saas/jobs/export.py`, replace the `export_data` dict in `export_json` (lines 52-62):

```python
    import json
    export_data = {
        "job_id": job.id,
        "goal": job.goal,
        "tier": job.tier,
        "report": job.result_report,
        "chat_log": json.loads(job.result_chat_log) if job.result_chat_log else [],
        "graph": json.loads(job.result_graph) if job.result_graph else None,
        "structured": json.loads(job.result_structured) if job.result_structured else None,
        "enriched_seed": job.enriched_seed,
        "enrichment_citations": (
            json.loads(job.enrichment_citations) if job.enrichment_citations else []
        ),
        "key_insight": job.key_insight,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_export_endpoints.py -v`
Expected: PASS. If any existing test asserted `export_data.keys() == {...}` exactly, update the expected set.

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/export.py tests/test_export_endpoints.py
git commit -m "feat(export): include structured, enrichment, and key_insight in JSON export"
```

---

## Task 10: Update demo importer to write new structured shape

**Files:**
- Modify: `infra/scripts/import_demos.py` (wherever `result_structured` is assembled)
- Test: `tests/test_demos_import.py` (create — unit-level, no live DB)

- [ ] **Step 1: Inspect current importer shape**

Run: `grep -n "result_structured\|structured" infra/scripts/import_demos.py`
Note which function builds the structured dict and which golden-demo files it reads.

- [ ] **Step 2: Write failing test — importer emits 5-key structured shape**

Create `tests/test_demos_import.py`:

```python
"""Verify the demo importer writes structured dicts compatible with the
post-cutover SimulationResults template (brief/findings/confidence/coalitions/
sentiment). Prevents regression where imported demos rendered old-shape cards."""
from __future__ import annotations

import json

from infra.scripts.import_demos import build_structured_payload


def test_build_structured_payload_has_required_keys():
    # build_structured_payload must accept the same minimal inputs tasks_report
    # uses: executive brief string, findings list, chat_log list, graph dict.
    payload = build_structured_payload(
        brief="demo brief",
        findings=[{"title": "F1", "content": "body"}],
        chat_log=[],
        graph_data={"nodes": [], "edges": [],
                    "metadata": {"total_nodes": 0, "total_edges": 0, "entity_types": []}},
    )
    data = json.loads(payload) if isinstance(payload, str) else payload
    assert {"brief", "findings", "confidence", "coalitions", "sentiment"} <= set(data)
    assert data["brief"] == "demo brief"
    assert all("accentColor" in f for f in data["findings"])
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/test_demos_import.py -v`
Expected: FAIL — either `build_structured_payload` doesn't exist or it emits the old shape.

- [ ] **Step 4: Rewrite the structured builder in `import_demos.py`**

In `infra/scripts/import_demos.py`, replace whatever local code builds the structured dict with a thin wrapper over `adapt_structured`:

```python
# near top imports
from simswarm.adapter import adapt_structured
import json as _json

def build_structured_payload(
    brief: str,
    findings: list[dict],
    chat_log: list[dict],
    graph_data: dict,
) -> str:
    """Demo-import wrapper — same contract as saas/jobs/tasks_report._build_structured."""
    return _json.dumps(adapt_structured(
        brief=brief, findings=findings,
        chat_log=chat_log, graph_data=graph_data,
    ))
```

Then update the site that currently passes `result_structured` to the INSERT to use `build_structured_payload(...)` instead of the inline old-shape dict.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_demos_import.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add infra/scripts/import_demos.py tests/test_demos_import.py
git commit -m "fix(demos): import demo rows with new 5-key structured shape"
```

---

## Final verification

- [ ] **Step 1: Full backend test suite**

Run: `pytest -q`
Expected: all PASS.

- [ ] **Step 2: Full frontend test suite**

Run: `cd frontend && npm test`
Expected: all PASS.

- [ ] **Step 3: Manual smoke on a completed job (staging)**

Trigger a tier=small sim; after REPORTING finishes, verify on the results page:

- Executive Brief renders above findings
- ConfidenceGrid shows 4 tiles (agents/rounds/graph entities/trades)
- Finding cards show description + metric + accent color
- Agent Coalitions section renders if any mutual-follow pairs exist
- Graph detail panel shows stance + influence multiplier for clicked node
- Chat replay shows post text, not raw JSON
- During the run, SimulationStatus shows `round=N/15` and pipeline stage dots advance
- `/jobs/<id>/export/json` contains `structured`, `enriched_seed`, `enrichment_citations`, `key_insight`
