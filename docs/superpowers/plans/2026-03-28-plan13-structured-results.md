# Structured Results & Graph Detail Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Story tab show structured visual components (findings, sentiment, coalitions, confidence) derived from existing pipeline data, and make the Graph tab detail panel show node relationships built from edge data.

**Architecture:** `build_structured_results()` in run_job.py extracts structured data from outline.json + chat_log + graph_data (no LLM). New `result_structured` JSON column persisted via worker pipeline. Frontend Story view renders structured components with markdown fallback. Graph detail panel builds relationships from edges client-side.

**Tech Stack:** Python (run_job.py), FastAPI, SQLAlchemy, Alembic, Vue 3, Cytoscape.js

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `infra/docker/run_job.py` | Modify | Add `build_structured_results()`, write `structured_results.json` |
| `infra/docker/worker_api.py` | Modify | Read `structured_results.json` in result payload |
| `saas/models/job.py` | Modify | Add `result_structured` column |
| `saas/schemas/jobs.py` | Modify | Add `result_structured` to JobResponse |
| `saas/workers/persistence.py` | Modify | Persist `result_structured` in `_save_job_results` |
| `saas/workers/job_runner.py` | Modify | Pass `structured` through result dict |
| `alembic/versions/` | Create | Migration for `result_structured` column |
| `frontend/src/components/graph/graphColors.js` | Modify | Expand entity type color map |
| `frontend/src/views/SimulationResults.vue` | Modify | Build node relationships, render structured Story |
| `tests/test_structured_results.py` | Create | Backend tests for build + persist |

---

### Task 1: build_structured_results() in run_job.py

**Files:**
- Modify: `infra/docker/run_job.py`
- Test: `tests/test_structured_results.py`

- [ ] **Step 1: Write test for build_structured_results**

```python
# tests/test_structured_results.py
"""Tests for structured result extraction from pipeline outputs."""
import json


def test_build_structured_results_from_outline_and_chat():
    """build_structured_results extracts brief, findings, sentiment, coalitions, confidence."""
    import sys
    from pathlib import Path
    from unittest.mock import patch, MagicMock

    infra_docker = str(Path(__file__).parent.parent / "infra" / "docker")
    if infra_docker not in sys.path:
        sys.path.insert(0, infra_docker)

    # Mock MiroFish imports
    with patch.dict(sys.modules, {
        "app": MagicMock(), "app.services": MagicMock(),
        "app.services.zep_tools": MagicMock(),
        "app.services.ontology_generator": MagicMock(),
        "app.services.graph_builder": MagicMock(),
        "app.services.text_processor": MagicMock(),
        "app.services.simulation_manager": MagicMock(),
        "app.services.simulation_runner": MagicMock(),
        "app.services.report_agent": MagicMock(),
        "app.config": MagicMock(),
    }):
        if "run_job" in sys.modules:
            del sys.modules["run_job"]
        import run_job

        outline = {
            "title": "Test Report",
            "summary": "This is the executive brief summarizing findings.",
            "sections": [
                {"title": "Market Impact", "content": ""},
                {"title": "Political Response", "content": ""},
            ],
        }

        section_contents = {
            "section_01.md": "Markets reacted sharply to the announcement. Oil prices surged 15% within hours.",
            "section_02.md": "Political leaders issued statements condemning the action. NATO called an emergency session.",
        }

        chat_log = [
            {"agent_name": "Agent_1", "action_type": "CREATE_POST", "platform": "twitter", "action_args": {"content": "test"}},
            {"agent_name": "Agent_2", "action_type": "LIKE_POST", "platform": "twitter", "action_args": {}},
            {"agent_name": "Agent_3", "action_type": "CREATE_POST", "platform": "reddit", "action_args": {"content": "test"}},
            {"agent_name": "Agent_1", "action_type": "FOLLOW", "platform": "twitter", "action_args": {"target": "Agent_2"}},
            {"agent_name": "Agent_2", "action_type": "FOLLOW", "platform": "twitter", "action_args": {"target": "Agent_1"}},
        ]

        graph_data = {
            "nodes": [{"uuid": "n1", "name": "A", "labels": ["Person"]}],
            "edges": [{"uuid": "e1", "name": "KNOWS", "source_node_uuid": "n1", "target_node_uuid": "n1"}],
            "metadata": {"total_nodes": 1, "total_edges": 1, "entity_types": ["Person"]},
        }

        result = run_job.build_structured_results(
            outline=outline,
            section_contents=section_contents,
            chat_log=chat_log,
            graph_data=graph_data,
        )

        assert result["brief"] == "This is the executive brief summarizing findings."
        assert len(result["findings"]) == 2
        assert result["findings"][0]["title"] == "Market Impact"
        assert "Markets reacted" in result["findings"][0]["description"]
        assert len(result["sentiment"]) > 0
        assert len(result["confidence"]) >= 3
        assert any(c["label"] == "Agents" for c in result["confidence"])


def test_build_structured_results_empty_inputs():
    """build_structured_results handles empty/missing data gracefully."""
    import sys
    from pathlib import Path
    from unittest.mock import patch, MagicMock

    infra_docker = str(Path(__file__).parent.parent / "infra" / "docker")
    if infra_docker not in sys.path:
        sys.path.insert(0, infra_docker)

    with patch.dict(sys.modules, {
        "app": MagicMock(), "app.services": MagicMock(),
        "app.services.zep_tools": MagicMock(),
        "app.services.ontology_generator": MagicMock(),
        "app.services.graph_builder": MagicMock(),
        "app.services.text_processor": MagicMock(),
        "app.services.simulation_manager": MagicMock(),
        "app.services.simulation_runner": MagicMock(),
        "app.services.report_agent": MagicMock(),
        "app.config": MagicMock(),
    }):
        if "run_job" in sys.modules:
            del sys.modules["run_job"]
        import run_job

        result = run_job.build_structured_results(
            outline=None,
            section_contents={},
            chat_log=[],
            graph_data={"nodes": [], "edges": [], "metadata": {"total_nodes": 0, "total_edges": 0}},
        )

        assert result["brief"] == ""
        assert result["findings"] == []
        assert result["sentiment"] == []
        assert result["coalitions"] == []
        assert len(result["confidence"]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_structured_results.py -v`
Expected: FAIL — `build_structured_results` not defined

- [ ] **Step 3: Implement build_structured_results in run_job.py**

Add before `run_pipeline()` in `infra/docker/run_job.py`:

```python
FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]


def build_structured_results(
    outline: dict | None,
    section_contents: dict[str, str],
    chat_log: list[dict],
    graph_data: dict,
) -> dict:
    """Build structured results from pipeline outputs. No LLM calls needed."""

    # --- Brief ---
    brief = ""
    if outline and outline.get("summary"):
        brief = outline["summary"]

    # --- Findings (from outline sections + section content) ---
    findings = []
    sections = (outline or {}).get("sections", [])
    sorted_files = sorted(section_contents.keys())
    for i, section in enumerate(sections):
        content = ""
        if i < len(sorted_files):
            raw = section_contents[sorted_files[i]]
            # First paragraph as description
            paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip() and not p.strip().startswith("#")]
            content = paragraphs[0] if paragraphs else ""
        findings.append({
            "label": "FINDING",
            "title": section.get("title", f"Section {i + 1}"),
            "description": content[:500],
            "metric": "",
            "accentColor": FINDING_COLORS[i % len(FINDING_COLORS)],
        })

    # --- Sentiment (from chat_log action types per platform) ---
    sentiment = []
    platform_actions: dict[str, dict[str, int]] = {}
    for action in chat_log:
        platform = action.get("platform", "unknown")
        action_type = action.get("action_type", "")
        if platform not in platform_actions:
            platform_actions[platform] = {"positive": 0, "total": 0}
        platform_actions[platform]["total"] += 1
        if action_type in ("CREATE_POST", "LIKE_POST", "REPOST", "COMMENT"):
            platform_actions[platform]["positive"] += 1

    for platform, counts in platform_actions.items():
        total = counts["total"]
        positive = counts["positive"]
        value = int((positive / total) * 100) if total > 0 else 0
        sentiment.append({
            "label": platform.capitalize(),
            "value": value,
            "direction": "positive" if value >= 50 else "negative",
        })

    # --- Coalitions (from FOLLOW patterns) ---
    coalitions = []
    follow_graph: dict[str, set[str]] = {}
    agent_names: set[str] = set()
    for action in chat_log:
        name = action.get("agent_name", "")
        if name:
            agent_names.add(name)
        if action.get("action_type") == "FOLLOW":
            target = action.get("action_args", {}).get("target", "")
            if name and target:
                follow_graph.setdefault(name, set()).add(target)

    # Find mutual follows (simple coalition detection)
    visited: set[str] = set()
    coalition_colors = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B"]
    ci = 0
    for agent in follow_graph:
        if agent in visited:
            continue
        group = {agent}
        for target in follow_graph.get(agent, set()):
            if agent in follow_graph.get(target, set()):
                group.add(target)
        if len(group) >= 2:
            visited.update(group)
            coalitions.append({
                "name": f"Coalition {ci + 1}",
                "description": f"Mutual followers: {', '.join(sorted(group))}",
                "agents": len(group),
                "strength": min(100, len(group) * 20),
                "color": coalition_colors[ci % len(coalition_colors)],
            })
            ci += 1

    # --- Confidence (simulation metadata) ---
    meta = graph_data.get("metadata", {})
    confidence = [
        {"label": "Agents", "value": str(len(agent_names)), "color": "#22D3EE"},
        {"label": "Rounds", "value": str(len(chat_log)), "color": "#A78BFA"},
        {"label": "Graph Entities", "value": str(meta.get("total_nodes", 0)), "color": "#6EE7B7"},
    ]

    return {
        "brief": brief,
        "findings": findings,
        "sentiment": sentiment,
        "coalitions": coalitions,
        "confidence": confidence,
    }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_structured_results.py -v`
Expected: 2 PASS

- [ ] **Step 5: Update run_pipeline() to call build_structured_results**

In `run_pipeline()`, after `graph_data = extract_graph_data(graph_id)`, add:

```python
    # Build structured results from pipeline outputs
    structured = {}
    try:
        # Read outline.json if it exists
        report_dirs = list(out.parent.glob("report_*"))
        outline = None
        section_contents = {}
        for rd in report_dirs:
            outline_file = rd / "outline.json"
            if outline_file.exists():
                outline = json.loads(outline_file.read_text(encoding="utf-8"))
            for sf in sorted(rd.glob("section_*.md")):
                section_contents[sf.name] = sf.read_text(encoding="utf-8")

        structured = build_structured_results(
            outline=outline,
            section_contents=section_contents,
            chat_log=chat_log,
            graph_data=graph_data,
        )
        print(f"[run_job] Structured results: {len(structured.get('findings', []))} findings, {len(structured.get('coalitions', []))} coalitions", flush=True)
    except Exception as exc:
        print(f"[run_job] WARNING: structured results extraction failed: {exc}", flush=True)

    structured_str = json.dumps(structured, ensure_ascii=False, default=str)
    (out / "structured_results.json").write_text(structured_str, encoding="utf-8")
```

Update the `summary` dict to include structured results count, and return it.

- [ ] **Step 6: Commit**

```bash
git add infra/docker/run_job.py tests/test_structured_results.py
git commit -m "feat: build_structured_results from pipeline outputs (no LLM)"
```

---

### Task 2: Worker API + Persistence + Schema

**Files:**
- Modify: `infra/docker/worker_api.py:62-75`
- Modify: `saas/models/job.py`
- Modify: `saas/schemas/jobs.py`
- Modify: `saas/workers/persistence.py:48-85`
- Modify: `saas/workers/job_runner.py` (result dict)
- Create: Alembic migration

- [ ] **Step 1: Update worker_api.py to read structured_results.json**

In the `_run_pipeline` function, after reading `graph_data.json`, add:

```python
        structured = "{}"
        if (results_dir / "structured_results.json").exists():
            structured = (results_dir / "structured_results.json").read_text()
```

Update the result dict:
```python
        with _lock:
            _job["status"] = "completed"
            _job["result"] = {"report": report, "chat_log": chat_log, "graph_data": graph_data, "structured": structured}
```

Also update the `/status` endpoint to include `structured` in the response when completed.

- [ ] **Step 2: Add result_structured column to SimulationJob**

In `saas/models/job.py`, add after `share_token`:

```python
    result_structured: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Add result_structured to JobResponse schema**

In `saas/schemas/jobs.py`, add to `JobResponse`:

```python
    result_structured: str | None = None
```

- [ ] **Step 4: Update persistence to save result_structured**

In `saas/workers/persistence.py`, update `_save_job_results` signature and SQL:

```python
def _save_job_results(job_id: int, report: str, chat_log: str, graph_data: str = "{}", key_insight: str | None = None, structured: str | None = None) -> None:
```

Add `result_structured = :structured,` to the SQL UPDATE and `:structured` to the params dict.

- [ ] **Step 5: Update job_runner result dict**

In `saas/workers/job_runner.py`, update `_poll_until_complete` return dict to include `structured`:

```python
        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": result.get("report", ""),
            "chat_log": result.get("chat_log", "[]"),
            "graph_data": result.get("graph_data", "{}"),
            "structured": result.get("structured", "{}"),
            "status": "completed",
        }
```

Update the task in `saas/workers/tasks.py` (the `run_simulation_task`) to extract and pass `structured`:

```python
        structured = result.get("structured", "{}")
        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data, key_insight=key_insight, structured=structured)
```

- [ ] **Step 6: Create Alembic migration**

```python
# alembic/versions/f7g8h9i0j1k2_add_result_structured.py
"""add result_structured to simulation_jobs"""
from alembic import op
import sqlalchemy as sa

revision = 'f7g8h9i0j1k2'
down_revision = 'e6f7g8h9i0j1'

def upgrade():
    op.add_column('simulation_jobs', sa.Column('result_structured', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('simulation_jobs', 'result_structured')
```

- [ ] **Step 7: Write backend test**

Append to `tests/test_structured_results.py`:

```python
import pytest
from saas.models.job import SimulationJob, JobStatus


async def test_result_structured_in_job_response(client, auth_headers, db_session):
    """JobResponse includes result_structured when present."""
    structured = json.dumps({"brief": "Test brief", "findings": []})
    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test", goal="test", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report", result_structured=structured,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["result_structured"])
    assert parsed["brief"] == "Test brief"


async def test_result_structured_null_for_old_jobs(client, auth_headers, db_session):
    """Old jobs without result_structured return null."""
    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test", goal="test", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        result_report="# Report",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["result_structured"] is None
```

- [ ] **Step 8: Run all tests**

Run: `pytest tests/test_structured_results.py tests/test_jobs_api.py -v`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add saas/models/job.py saas/schemas/jobs.py saas/workers/persistence.py saas/workers/job_runner.py saas/workers/tasks.py infra/docker/worker_api.py alembic/versions/ tests/test_structured_results.py
git commit -m "feat: persist result_structured through worker pipeline (#11)"
```

---

### Task 3: Expand Graph Entity Type Colors

**Files:**
- Modify: `frontend/src/components/graph/graphColors.js`

- [ ] **Step 1: Replace ENTITY_COLORS with expanded mapping**

```javascript
const ENTITY_COLORS = {
  // People
  Person: '#A78BFA',
  PoliticalFigure: '#A78BFA',
  PrimeMinister: '#A78BFA',
  GovernmentOfficial: '#A78BFA',
  JudicialFigure: '#818CF8',
  OpinionLeader: '#FBBF24',

  // Organizations
  Organization: '#22D3EE',
  GovernmentAgency: '#FF6B6B',
  InternationalOrganization: '#14B8A6',
  RegulatoryAgency: '#10B981',
  LegalAuthority: '#10B981',

  // Media
  MediaOutlet: '#6EE7B7',
  MediaOutlets: '#6EE7B7',

  // Military
  MilitaryUnit: '#EF4444',
  CoalitionMember: '#F97316',

  // Business
  EnergyCompany: '#FBBF24',
  ShippingCompany: '#38BDF8',
  Airline: '#38BDF8',

  // Places
  Country: '#8B5CF6',
  City: '#C084FC',
  Location: '#C084FC',

  // Academic
  University: '#F97316',
  Professor: '#F97316',
  Student: '#FF6B6B',
  Alumni: '#FF6B6B',

  // Generic fallback
  Entity: '#6B7280',
}
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/graph/graphColors.js
git commit -m "feat: expand entity type color mapping for Zep-produced types"
```

---

### Task 4: Graph Detail Panel — Build Node Relationships from Edges

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Add relationship-building function**

In `SimulationResults.vue`, in the `<script setup>` section, add a function that builds relationships from edges and attaches them to nodes. Call it after graph data is fetched.

```javascript
function buildNodeRelationships(nodes, edges) {
  const relMap = {}
  for (const edge of edges) {
    if (!relMap[edge.source_node_uuid]) relMap[edge.source_node_uuid] = []
    relMap[edge.source_node_uuid].push({
      direction: 'outgoing',
      type: edge.name || edge.fact || '',
      target_uuid: edge.target_node_uuid,
      targetName: edge.target_node_name || '',
      fact: edge.fact || '',
    })
    if (!relMap[edge.target_node_uuid]) relMap[edge.target_node_uuid] = []
    relMap[edge.target_node_uuid].push({
      direction: 'incoming',
      type: edge.name || edge.fact || '',
      source_uuid: edge.source_node_uuid,
      sourceName: edge.source_node_name || '',
      fact: edge.fact || '',
    })
  }
  return nodes.map(n => ({
    ...n,
    relationships: relMap[n.uuid] || [],
  }))
}
```

Call this when setting graph data (where `graphData` is populated from the API). Pass the enriched nodes to GraphVisualization.

- [ ] **Step 2: Add node properties to GraphDetailPanel**

In `frontend/src/components/graph/GraphDetailPanel.vue`, add a Properties section before the Relationships section:

```vue
<!-- Properties -->
<div class="mb-4">
  <h4 class="text-[10px] font-bold tracking-wider text-mist-slate uppercase mb-2">Properties</h4>
  <div class="flex justify-between text-xs py-0.5">
    <span class="text-mist-slate">type</span>
    <span class="text-mist-drift">{{ node.entityType }}</span>
  </div>
  <div class="flex justify-between text-xs py-0.5">
    <span class="text-mist-slate">connections</span>
    <span class="text-mist-drift">{{ node.connectionCount }}</span>
  </div>
</div>
```

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/SimulationResults.vue frontend/src/components/graph/GraphDetailPanel.vue
git commit -m "feat: build node relationships from edges, show properties in detail panel"
```

---

### Task 5: Story View — Render Structured Components

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Parse result_structured in the view**

Add a computed property that parses the structured results:

```javascript
const structured = computed(() => {
  if (!job.value?.result_structured) return null
  try {
    return typeof job.value.result_structured === 'string'
      ? JSON.parse(job.value.result_structured)
      : job.value.result_structured
  } catch {
    return null
  }
})
```

- [ ] **Step 2: Render structured components in Story view**

In the Story view template section, add a conditional block that renders the structured components when data is present, falling back to the existing ReportViewer:

```vue
<template v-if="structured">
  <!-- Executive Brief -->
  <div v-if="structured.brief" class="mb-8">
    <h2 class="text-lg font-bold text-mist-foam mb-3">Executive Brief</h2>
    <p class="text-sm text-mist-drift leading-relaxed">{{ structured.brief }}</p>
  </div>

  <!-- Confidence Grid -->
  <ConfidenceGrid v-if="structured.confidence?.length" :items="structured.confidence" class="mb-8" />

  <!-- Key Findings -->
  <div v-if="structured.findings?.length" class="mb-8">
    <h2 class="text-lg font-bold text-mist-foam mb-4">Key Findings</h2>
    <div class="grid gap-4">
      <FindingCard
        v-for="(finding, i) in structured.findings"
        :key="i"
        :label="finding.label"
        :title="finding.title"
        :description="finding.description"
        :metric="finding.metric"
        :accent-color="finding.accentColor"
      />
    </div>
  </div>

  <!-- Sentiment -->
  <SentimentBars
    v-if="structured.sentiment?.length"
    :bars="sentimentBars"
    class="mb-8"
  />

  <!-- Coalitions -->
  <div v-if="structured.coalitions?.length" class="mb-8">
    <h2 class="text-lg font-bold text-mist-foam mb-4">Agent Coalitions</h2>
    <div class="grid gap-4 md:grid-cols-2">
      <CoalitionCard
        v-for="(c, i) in structured.coalitions"
        :key="i"
        :name="c.name"
        :description="c.description"
        :agents="c.agents"
        :strength="c.strength"
        :color="c.color"
      />
    </div>
  </div>

  <!-- Full report below structured view -->
  <ReportViewer :content="job.result_report || ''" />
</template>

<!-- Fallback: no structured data -->
<template v-else>
  <ReportViewer :content="job.result_report || ''" />
</template>
```

Add a computed for SentimentBars format (transform structured.sentiment to the bar format):

```javascript
const sentimentBars = computed(() => {
  if (!structured.value?.sentiment) return []
  return structured.value.sentiment.map(s => ({
    label: s.label,
    width: s.value,
    value: `${s.value}%`,
    gradient: s.direction === 'positive'
      ? 'linear-gradient(90deg, #22D3EE, #6EE7B7)'
      : 'linear-gradient(90deg, #FF6B6B, #F97316)',
    valueColor: s.direction === 'positive' ? '#6EE7B7' : '#FF6B6B',
  }))
})
```

- [ ] **Step 3: Import the structured components**

Add imports at the top of the script:

```javascript
import FindingCard from '@/components/results/FindingCard.vue'
import SentimentBars from '@/components/results/SentimentBars.vue'
import CoalitionCard from '@/components/results/CoalitionCard.vue'
import ConfidenceGrid from '@/components/results/ConfidenceGrid.vue'
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SimulationResults.vue
git commit -m "feat: render structured Story view with findings, sentiment, coalitions (#11)"
```

---

### Task 6: Full Test Suite Verification

- [ ] **Step 1: Run backend tests**

Run: `pytest tests/ -v --tb=short`
Expected: All pass (255+)

- [ ] **Step 2: Lint**

Run: `ruff check saas/ tests/`
Expected: Clean

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: No errors

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "fix: lint and test fixups for structured results"
```
