# Graph Relationship Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive Cytoscape.js graph visualization to the simulation results page, showing entities and relationships extracted from the MiroFish Zep graph.

**Architecture:** Backend extracts graph data (nodes + edges) from Zep before the ephemeral graph is destroyed, stores as JSON in a new DB column, and exposes via a dedicated API endpoint. Frontend adds a `GraphVisualization` Vue component with Cytoscape.js rendering, multiple layout modes (full-screen graph, dual-column, report-only), interactive controls, and entity type filtering.

**Tech Stack:** Vue 3 (Composition API), Cytoscape.js + cose-bilkent + dagre extensions, Tailwind CSS, Python/FastAPI, SQLAlchemy, Alembic

---

## File Structure

### Backend (new/modified)
- **Create:** `saas/schemas/graph.py` — Pydantic schemas for graph API response (GraphNode, GraphEdge, GraphMetadata, GraphResponse)
- **Modify:** `saas/models/job.py:28` — Add `result_graph` column to SimulationJob
- **Modify:** `saas/api/jobs.py` — Add `GET /jobs/{job_id}/graph` endpoint
- **Modify:** `saas/schemas/jobs.py` — Add `has_graph` field to JobResponse
- **Create:** `alembic/versions/add_result_graph_column.py` — Alembic migration
- **Modify:** `saas/workers/tasks.py:75-113` — Add graph_data to `_save_job_results()`
- **Modify:** `saas/workers/job_runner.py:224-233` — Pass graph_data in result dict
- **Modify:** `infra/docker/worker_api.py:61-72` — Read and return graph_data.json
- **Modify:** `infra/docker/run_job.py:336-361` — Extract graph data before pipeline returns

### Frontend (new/modified)
- **Modify:** `frontend/package.json` — Add cytoscape, cytoscape-cose-bilkent, cytoscape-dagre
- **Modify:** `frontend/src/api/jobs.js` — Add `getJobGraph()` function
- **Create:** `frontend/src/components/graph/graphColors.js` — Entity type → color mapping + dynamic color assignment
- **Create:** `frontend/src/components/graph/GraphCanvas.vue` — Cytoscape.js renderer with layout, styling, hover/click
- **Create:** `frontend/src/components/graph/GraphControls.vue` — Toolbar: refresh, fullscreen, edge labels, layout selector, export
- **Create:** `frontend/src/components/graph/GraphSearchBar.vue` — Autocomplete node search
- **Create:** `frontend/src/components/graph/GraphLegend.vue` — Entity type legend with filter toggles
- **Create:** `frontend/src/components/graph/GraphDetailPanel.vue` — Slide-in panel showing node details + relationships
- **Create:** `frontend/src/components/graph/GraphVisualization.vue` — Main container orchestrating all graph sub-components
- **Create:** `frontend/src/components/ViewModeToggle.vue` — Graph/Dual Column/Report mode switcher
- **Modify:** `frontend/src/views/SimulationResults.vue` — Integrate ViewModeToggle, GraphVisualization, dual-column layout
- **Modify:** `frontend/src/views/DemoResult.vue` — Add graph visualization for demo pages

---

## Task 1: Backend — Database Migration & Model

**Files:**
- Modify: `saas/models/job.py:28-29`
- Create: `alembic/versions/add_result_graph_column.py`

- [ ] **Step 1: Add result_graph column to SimulationJob model**

In `saas/models/job.py`, add after line 29 (`result_chat_log`):

```python
    result_graph: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Create Alembic migration**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat
alembic revision --autogenerate -m "add result_graph column to simulation_jobs"
```

If autogenerate doesn't work (no DB connection), create manually as `alembic/versions/b3f4g5h6i7j8_add_result_graph.py`:

```python
"""add result_graph column to simulation_jobs

Revision ID: b3f4g5h6i7j8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3f4g5h6i7j8'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('simulation_jobs', sa.Column('result_graph', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('simulation_jobs', 'result_graph')
```

Note: Check the latest revision ID in `alembic/versions/` and set `down_revision` accordingly. The current latest is `a1b2c3d4e5f6` (email verification migration).

- [ ] **Step 3: Commit**

```bash
git add saas/models/job.py alembic/versions/*result_graph*
git commit -m "feat: add result_graph column to SimulationJob model"
```

---

## Task 2: Backend — Graph Extraction in Pipeline

**Files:**
- Modify: `infra/docker/run_job.py:336-361`
- Modify: `infra/docker/worker_api.py:61-72`

- [ ] **Step 1: Add graph extraction to run_job.py**

In `infra/docker/run_job.py`, add a new function before `run_pipeline()` (before line 336):

```python
def extract_graph_data(graph_id: str) -> dict:
    """Extract all nodes and edges from the Zep graph for visualization."""
    from app.services.zep_tools import ZepToolService
    import os

    zep_api_key = os.getenv("ZEP_API_KEY", "")
    if not zep_api_key:
        print("[graph] No ZEP_API_KEY, skipping graph extraction")
        return {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}

    try:
        zep_tools = ZepToolService(api_key=zep_api_key)
        all_nodes = zep_tools.get_all_nodes(graph_id)
        all_edges = zep_tools.get_all_edges(graph_id)

        # Build connection count per node
        connection_counts = {}
        for edge in all_edges:
            connection_counts[edge.source_node_uuid] = connection_counts.get(edge.source_node_uuid, 0) + 1
            connection_counts[edge.target_node_uuid] = connection_counts.get(edge.target_node_uuid, 0) + 1

        # Collect entity types
        entity_types = set()
        nodes = []
        for node in all_nodes:
            primary_label = next((l for l in node.labels if l not in ("Entity", "Node")), "Entity")
            entity_types.add(primary_label)
            nodes.append({
                "uuid": node.uuid,
                "name": node.name,
                "labels": node.labels,
                "summary": node.summary,
                "connection_count": connection_counts.get(node.uuid, 0),
            })

        edges = []
        for edge in all_edges:
            edges.append({
                "uuid": edge.uuid,
                "name": edge.name,
                "fact": edge.fact,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "source_node_name": edge.source_node_name,
                "target_node_name": edge.target_node_name,
            })

        graph_data = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "entity_types": sorted(entity_types),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        }
        print(f"[graph] Extracted {len(nodes)} nodes, {len(edges)} edges")
        return graph_data

    except Exception as e:
        print(f"[graph] Failed to extract graph data: {e}")
        return {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}
```

- [ ] **Step 2: Call graph extraction in run_pipeline()**

In `infra/docker/run_job.py`, modify `run_pipeline()` (around line 344). Add graph extraction after `report_md` is generated and before writing results:

Replace lines 347-358 with:

```python
    # Extract graph data before Zep teardown
    graph_data = extract_graph_data(graph_id)

    (out / "report.md").write_text(report_md, encoding="utf-8")
    chat_log_str = json.dumps(chat_log, ensure_ascii=False, default=str)
    (out / "chat_log.json").write_text(chat_log_str, encoding="utf-8")
    graph_data_str = json.dumps(graph_data, ensure_ascii=False, default=str)
    (out / "graph_data.json").write_text(graph_data_str, encoding="utf-8")

    summary = {
        "status": "completed",
        "simulation_id": simulation_id,
        "graph_id": graph_id,
        "report_length": len(report_md),
        "chat_log_entries": len(chat_log),
        "graph_nodes": len(graph_data.get("nodes", [])),
        "graph_edges": len(graph_data.get("edges", [])),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
```

- [ ] **Step 3: Read graph_data.json in worker_api.py**

In `infra/docker/worker_api.py`, modify the result reading section (lines 61-72). Add after the `chat_log` read:

```python
        # Read results
        results_dir = Path("/tmp/results")
        report = ""
        chat_log = "[]"
        graph_data = "{}"
        if (results_dir / "report.md").exists():
            report = (results_dir / "report.md").read_text()
        if (results_dir / "chat_log.json").exists():
            chat_log = (results_dir / "chat_log.json").read_text()
        if (results_dir / "graph_data.json").exists():
            graph_data = (results_dir / "graph_data.json").read_text()

        with _lock:
            _job["status"] = "completed"
            _job["result"] = {"report": report, "chat_log": chat_log, "graph_data": graph_data}
```

And in the `/status` endpoint (line 134), add `graph_data`:

```python
@app.route("/status", methods=["GET"])
def job_status():
    """Poll for completion. Returns report + chat_log + graph_data when done."""
    with _lock:
        resp = {"status": _job["status"]}
        if _job["status"] == "completed" and _job["result"]:
            resp["report"] = _job["result"]["report"]
            resp["chat_log"] = _job["result"]["chat_log"]
            resp["graph_data"] = _job["result"].get("graph_data", "{}")
        if _job["status"] == "failed":
            resp["error"] = _job["error"]
    return jsonify(resp)
```

- [ ] **Step 4: Commit**

```bash
git add infra/docker/run_job.py infra/docker/worker_api.py
git commit -m "feat: extract graph data from Zep before teardown"
```

---

## Task 3: Backend — Persist Graph Data & API Endpoint

**Files:**
- Modify: `saas/workers/job_runner.py:224-233`
- Modify: `saas/workers/tasks.py:75-113` and `261-264`
- Create: `saas/schemas/graph.py`
- Modify: `saas/schemas/jobs.py:35-50`
- Modify: `saas/api/jobs.py`

- [ ] **Step 1: Pass graph_data through JobRunner**

In `saas/workers/job_runner.py`, modify the return dict (lines 227-233):

```python
        return {
            "job_id": config.job_id,
            "instance_id": instance_id,
            "report": result.get("report", ""),
            "chat_log": result.get("chat_log", "[]"),
            "graph_data": result.get("graph_data", "{}"),
            "status": "completed",
        }
```

- [ ] **Step 2: Update _save_job_results to include graph_data**

In `saas/workers/tasks.py`, modify `_save_job_results` signature and SQL (lines 75-113):

```python
def _save_job_results(job_id: int, report: str, chat_log: str, graph_data: str = "{}") -> None:
    """Persist pipeline results (report + chat_log + graph_data) to the SimulationJob row."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping result save for job %d", job_id)
        return

    async def _do_save():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET status = 'COMPLETED', "
                        "    result_report = :report, "
                        "    result_chat_log = :chat_log, "
                        "    result_graph = :graph_data, "
                        "    completed_at = :completed_at "
                        "WHERE id = :job_id"
                    ),
                    {
                        "report": report,
                        "chat_log": chat_log,
                        "graph_data": graph_data,
                        "completed_at": datetime.now(timezone.utc),
                        "job_id": job_id,
                    },
                )
                await session.commit()
                logger.info("Saved results for job %d", job_id)
            except Exception as exc:
                logger.warning("Could not save results for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_save())
```

And update the call site (around line 262-264):

```python
        report = result.get("report", "")
        chat_log = result.get("chat_log", "")
        graph_data = result.get("graph_data", "{}")
        _save_job_results(job_id=job_id, report=report, chat_log=chat_log, graph_data=graph_data)
```

- [ ] **Step 3: Create graph schema**

Create `saas/schemas/graph.py`:

```python
from __future__ import annotations
from pydantic import BaseModel


class GraphNode(BaseModel):
    uuid: str
    name: str
    labels: list[str]
    summary: str
    connection_count: int


class GraphEdge(BaseModel):
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str | None = None
    target_node_name: str | None = None


class GraphMetadata(BaseModel):
    entity_types: list[str]
    total_nodes: int
    total_edges: int


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: GraphMetadata
```

- [ ] **Step 4: Add has_graph to JobResponse**

In `saas/schemas/jobs.py`, add to `JobResponse`:

```python
class JobResponse(BaseModel):
    id: int
    user_id: str
    seed_text: str
    goal: str
    tier: str
    credits_charged: int
    status: str
    pipeline_stage: int | None
    result_report: str | None = None
    result_chat_log: str | None = None
    has_graph: bool = False
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}

    @field_validator("has_graph", mode="before")
    @classmethod
    def compute_has_graph(cls, v, info):
        # When constructing from ORM, check if result_graph is populated
        if hasattr(info, 'data') and info.data.get('result_graph'):
            return True
        return bool(v)
```

Actually, since the ORM model doesn't have `has_graph`, use a simpler approach — add a computed property by using a model validator:

```python
from pydantic import BaseModel, field_validator, model_validator

class JobResponse(BaseModel):
    id: int
    user_id: str
    seed_text: str
    goal: str
    tier: str
    credits_charged: int
    status: str
    pipeline_stage: int | None
    result_report: str | None = None
    result_chat_log: str | None = None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    has_graph: bool = False

    model_config = {"from_attributes": True}
```

And in the API endpoint, set `has_graph` when constructing the response. Simplest approach: in the `get_job` endpoint, check `job.result_graph` before returning.

- [ ] **Step 5: Add graph endpoint to jobs API**

In `saas/api/jobs.py`, add after the `get_job` endpoint:

```python
import json
from saas.schemas.graph import GraphResponse

@router.get("/{job_id}/graph", response_model=GraphResponse)
async def get_job_graph(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    if not job.result_graph:
        raise HTTPException(status_code=404, detail="Graph data not available")

    graph_data = json.loads(job.result_graph)
    return graph_data
```

- [ ] **Step 6: Commit**

```bash
git add saas/workers/job_runner.py saas/workers/tasks.py saas/schemas/graph.py saas/schemas/jobs.py saas/api/jobs.py
git commit -m "feat: persist graph data and add GET /jobs/{id}/graph endpoint"
```

---

## Task 4: Frontend — Install Dependencies & API Client

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/api/jobs.js`

- [ ] **Step 1: Install Cytoscape.js packages**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/frontend
npm install cytoscape cytoscape-cose-bilkent cytoscape-dagre
```

- [ ] **Step 2: Add getJobGraph to API client**

In `frontend/src/api/jobs.js`, add:

```js
export async function getJobGraph(jobId) {
  const response = await api.get(`/jobs/${jobId}/graph`)
  return response.data
}
```

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json src/api/jobs.js
git commit -m "feat: add cytoscape dependencies and graph API client"
```

---

## Task 5: Frontend — Graph Color Mapping

**Files:**
- Create: `frontend/src/components/graph/graphColors.js`

- [ ] **Step 1: Create the color mapping module**

Create `frontend/src/components/graph/graphColors.js`:

```js
const ENTITY_COLORS = {
  University: '#f97316',
  Entity: '#1e40af',
  Alumni: '#991b1b',
  Organization: '#22c55e',
  Student: '#dc2626',
  Professor: '#ea580c',
  Person: '#3b82f6',
  MediaOutlet: '#7c3aed',
  LegalAuthority: '#16a34a',
  OpinionLeader: '#f59e0b',
  GovernmentAgency: '#b91c1c',
}

// Fallback palette for unknown entity types
const FALLBACK_PALETTE = [
  '#6366f1', '#ec4899', '#14b8a6', '#f43f5e', '#84cc16',
  '#a855f7', '#06b6d4', '#eab308', '#ef4444', '#10b981',
]

const dynamicColorCache = {}

export function getEntityColor(entityType) {
  if (ENTITY_COLORS[entityType]) return ENTITY_COLORS[entityType]
  if (dynamicColorCache[entityType]) return dynamicColorCache[entityType]

  // Hash the entity type name to pick a palette color
  let hash = 0
  for (let i = 0; i < entityType.length; i++) {
    hash = ((hash << 5) - hash + entityType.charCodeAt(i)) | 0
  }
  const color = FALLBACK_PALETTE[Math.abs(hash) % FALLBACK_PALETTE.length]
  dynamicColorCache[entityType] = color
  return color
}

export function getPrimaryLabel(labels) {
  return labels.find((l) => l !== 'Entity' && l !== 'Node') || 'Entity'
}

export { ENTITY_COLORS }
```

- [ ] **Step 2: Commit**

```bash
git add src/components/graph/graphColors.js
git commit -m "feat: add entity type color mapping for graph nodes"
```

---

## Task 6: Frontend — GraphCanvas Component (Cytoscape Renderer)

**Files:**
- Create: `frontend/src/components/graph/GraphCanvas.vue`

- [ ] **Step 1: Create the Cytoscape canvas component**

Create `frontend/src/components/graph/GraphCanvas.vue`:

```vue
<template>
  <div ref="containerRef" class="w-full h-full" />
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import dagre from 'cytoscape-dagre'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

cytoscape.use(coseBilkent)
cytoscape.use(dagre)

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'cose-bilkent' },
  selectedNodeId: { type: String, default: null },
})

const emit = defineEmits(['node-click', 'node-hover', 'node-unhover', 'ready'])

const containerRef = ref(null)
let cy = null

const LAYOUT_OPTIONS = {
  'cose-bilkent': {
    name: 'cose-bilkent',
    animate: 'end',
    animationDuration: 500,
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.25,
    numIter: 2500,
    tile: true,
    tilingPaddingVertical: 10,
    tilingPaddingHorizontal: 10,
  },
  circle: { name: 'circle', animate: true, animationDuration: 500 },
  dagre: { name: 'dagre', animate: true, animationDuration: 500, rankDir: 'TB', nodeSep: 60, rankSep: 80 },
  grid: { name: 'grid', animate: true, animationDuration: 500 },
}

function buildElements() {
  const nodeEls = props.nodes
    .filter((n) => !props.hiddenTypes.has(getPrimaryLabel(n.labels)))
    .map((n) => ({
      group: 'nodes',
      data: {
        id: n.uuid,
        label: n.name,
        entityType: getPrimaryLabel(n.labels),
        summary: n.summary,
        connectionCount: n.connection_count,
        color: getEntityColor(getPrimaryLabel(n.labels)),
        size: Math.max(20, Math.min(60, 20 + n.connection_count * 2)),
      },
    }))

  const visibleNodeIds = new Set(nodeEls.map((n) => n.data.id))
  const edgeEls = props.edges
    .filter((e) => visibleNodeIds.has(e.source_node_uuid) && visibleNodeIds.has(e.target_node_uuid))
    .map((e) => ({
      group: 'edges',
      data: {
        id: e.uuid,
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        label: e.name,
        fact: e.fact,
      },
    }))

  return [...nodeEls, ...edgeEls]
}

function initCytoscape() {
  if (!containerRef.value) return

  cy = cytoscape({
    container: containerRef.value,
    elements: buildElements(),
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          label: 'data(label)',
          width: 'data(size)',
          height: 'data(size)',
          'font-size': '11px',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          color: '#666',
          'text-outline-color': '#fff',
          'text-outline-width': 2,
          'min-zoomed-font-size': 8,
          'overlay-padding': 4,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1,
          'line-color': 'rgba(150,150,150,0.3)',
          'target-arrow-color': 'rgba(150,150,150,0.3)',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.6,
          'curve-style': 'bezier',
          label: props.showEdgeLabels ? 'data(label)' : '',
          'font-size': '9px',
          'text-rotation': 'autorotate',
          color: 'rgba(100,100,100,0.6)',
          'text-outline-color': '#fff',
          'text-outline-width': 1.5,
          'min-zoomed-font-size': 10,
        },
      },
      {
        selector: 'node.highlighted',
        style: {
          'border-width': 3,
          'border-color': '#4f46e5',
          'z-index': 10,
        },
      },
      {
        selector: 'node.neighbor',
        style: {
          opacity: 1,
        },
      },
      {
        selector: 'node.dimmed',
        style: {
          opacity: 0.2,
        },
      },
      {
        selector: 'edge.highlighted',
        style: {
          width: 2,
          'line-color': 'rgba(79,70,229,0.6)',
          'target-arrow-color': 'rgba(79,70,229,0.6)',
          'z-index': 10,
        },
      },
      {
        selector: 'edge.dimmed',
        style: {
          opacity: 0.1,
        },
      },
      {
        selector: 'node.selected-node',
        style: {
          'border-width': 4,
          'border-color': '#7c3aed',
          'z-index': 20,
        },
      },
    ],
    layout: LAYOUT_OPTIONS[props.layoutName] || LAYOUT_OPTIONS['cose-bilkent'],
    minZoom: 0.1,
    maxZoom: 5,
    wheelSensitivity: 0.3,
  })

  // Hover effects
  cy.on('mouseover', 'node', (e) => {
    const node = e.target
    const neighborhood = node.closedNeighborhood()
    cy.elements().not(neighborhood).addClass('dimmed')
    neighborhood.edges().addClass('highlighted')
    neighborhood.nodes().addClass('neighbor')
    node.addClass('highlighted')
    emit('node-hover', {
      id: node.id(),
      name: node.data('label'),
      entityType: node.data('entityType'),
      position: e.renderedPosition,
    })
  })

  cy.on('mouseout', 'node', () => {
    cy.elements().removeClass('dimmed highlighted neighbor')
    emit('node-unhover')
  })

  // Click to select
  cy.on('tap', 'node', (e) => {
    const node = e.target
    cy.nodes().removeClass('selected-node')
    node.addClass('selected-node')
    const connectedEdges = node.connectedEdges()
    const relationships = connectedEdges.map((edge) => ({
      name: edge.data('label'),
      fact: edge.data('fact'),
      sourceId: edge.source().id(),
      targetId: edge.target().id(),
      sourceName: edge.source().data('label'),
      targetName: edge.target().data('label'),
      direction: edge.source().id() === node.id() ? 'outgoing' : 'incoming',
    }))
    emit('node-click', {
      id: node.id(),
      name: node.data('label'),
      entityType: node.data('entityType'),
      summary: node.data('summary'),
      connectionCount: node.data('connectionCount'),
      relationships,
    })
  })

  // Click background to deselect
  cy.on('tap', (e) => {
    if (e.target === cy) {
      cy.nodes().removeClass('selected-node')
    }
  })

  emit('ready', cy)
}

function runLayout() {
  if (!cy) return
  const options = LAYOUT_OPTIONS[props.layoutName] || LAYOUT_OPTIONS['cose-bilkent']
  cy.layout(options).run()
}

function updateElements() {
  if (!cy) return
  cy.elements().remove()
  cy.add(buildElements())
  runLayout()
}

function focusNode(nodeId) {
  if (!cy) return
  const node = cy.getElementById(nodeId)
  if (node.length) {
    cy.animate({ center: { eles: node }, zoom: 2 }, { duration: 400 })
    cy.nodes().removeClass('selected-node')
    node.addClass('selected-node')
  }
}

function exportImage(format) {
  if (!cy) return null
  if (format === 'svg') return cy.svg({ full: true })
  return cy.png({ full: true, scale: 2, bg: '#ffffff' })
}

watch(() => props.hiddenTypes, updateElements, { deep: true })
watch(() => props.layoutName, runLayout)
watch(
  () => props.showEdgeLabels,
  (show) => {
    if (!cy) return
    cy.style().selector('edge').style('label', show ? 'data(label)' : '').update()
  }
)
watch(
  () => props.selectedNodeId,
  (id) => {
    if (id) focusNode(id)
  }
)

onMounted(() => {
  nextTick(() => initCytoscape())
})

onBeforeUnmount(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})

defineExpose({ runLayout, focusNode, exportImage, getCy: () => cy })
</script>
```

- [ ] **Step 2: Verify the component renders without errors**

This will be tested in integration after the parent component is built (Task 10).

- [ ] **Step 3: Commit**

```bash
git add src/components/graph/GraphCanvas.vue
git commit -m "feat: add GraphCanvas component with Cytoscape.js rendering"
```

---

## Task 7: Frontend — GraphControls Component

**Files:**
- Create: `frontend/src/components/graph/GraphControls.vue`

- [ ] **Step 1: Create the toolbar component**

Create `frontend/src/components/graph/GraphControls.vue`:

```vue
<template>
  <div class="absolute top-3 right-3 flex items-center gap-2 z-10">
    <!-- Refresh -->
    <button
      @click="$emit('refresh')"
      class="flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 shadow-sm"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      Refresh
    </button>

    <!-- Fullscreen -->
    <button
      @click="$emit('toggle-fullscreen')"
      class="p-1.5 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 shadow-sm"
      :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
    >
      <svg v-if="!isFullscreen" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
      </svg>
      <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
      </svg>
    </button>

    <!-- Edge Labels Toggle -->
    <label class="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 shadow-sm cursor-pointer">
      <div
        class="relative w-8 h-4 rounded-full transition-colors"
        :class="showEdgeLabels ? 'bg-indigo-500' : 'bg-gray-300'"
        @click="$emit('toggle-edge-labels')"
      >
        <div
          class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-transform"
          :class="showEdgeLabels ? 'translate-x-4' : 'translate-x-0.5'"
        />
      </div>
      Show Edge Labels
    </label>

    <!-- Layout Selector -->
    <select
      :value="layoutName"
      @change="$emit('change-layout', $event.target.value)"
      class="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 shadow-sm"
    >
      <option value="cose-bilkent">Force-directed</option>
      <option value="circle">Circular</option>
      <option value="dagre">Hierarchical</option>
      <option value="grid">Grid</option>
    </select>

    <!-- Export -->
    <div class="relative" ref="exportMenuRef">
      <button
        @click="showExportMenu = !showExportMenu"
        class="flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 shadow-sm"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Export
      </button>
      <div
        v-if="showExportMenu"
        class="absolute right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-20"
      >
        <button
          @click="$emit('export', 'png'); showExportMenu = false"
          class="block w-full text-left px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          Export as PNG
        </button>
        <button
          @click="$emit('export', 'svg'); showExportMenu = false"
          class="block w-full text-left px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          Export as SVG
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps({
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'cose-bilkent' },
  isFullscreen: { type: Boolean, default: false },
})

defineEmits(['refresh', 'toggle-fullscreen', 'toggle-edge-labels', 'change-layout', 'export'])

const showExportMenu = ref(false)
const exportMenuRef = ref(null)

function handleClickOutside(e) {
  if (exportMenuRef.value && !exportMenuRef.value.contains(e.target)) {
    showExportMenu.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))
</script>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/graph/GraphControls.vue
git commit -m "feat: add GraphControls toolbar component"
```

---

## Task 8: Frontend — GraphSearchBar Component

**Files:**
- Create: `frontend/src/components/graph/GraphSearchBar.vue`

- [ ] **Step 1: Create the search component**

Create `frontend/src/components/graph/GraphSearchBar.vue`:

```vue
<template>
  <div class="absolute top-3 left-3 z-10 w-64">
    <div class="relative">
      <svg class="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        v-model="query"
        @input="onInput"
        @focus="showDropdown = true"
        @keydown.escape="showDropdown = false"
        @keydown.enter="selectFirst"
        type="text"
        placeholder="Search entities..."
        class="w-full pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-lg text-sm shadow-sm focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 outline-none"
      />
    </div>
    <div
      v-if="showDropdown && filteredNodes.length > 0"
      class="absolute mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto z-20"
    >
      <button
        v-for="node in filteredNodes"
        :key="node.uuid"
        @click="selectNode(node)"
        class="flex items-center gap-2 w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
      >
        <span
          class="w-3 h-3 rounded-full flex-shrink-0"
          :style="{ backgroundColor: node.color }"
        />
        <span class="truncate">{{ node.name }}</span>
        <span class="text-gray-400 text-xs ml-auto">{{ node.entityType }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['select-node'])

const query = ref('')
const showDropdown = ref(false)

const enrichedNodes = computed(() =>
  props.nodes.map((n) => ({
    ...n,
    entityType: getPrimaryLabel(n.labels),
    color: getEntityColor(getPrimaryLabel(n.labels)),
  }))
)

const filteredNodes = computed(() => {
  if (!query.value.trim()) return enrichedNodes.value.slice(0, 20)
  const q = query.value.toLowerCase()
  return enrichedNodes.value
    .filter((n) => n.name.toLowerCase().includes(q) || n.entityType.toLowerCase().includes(q))
    .slice(0, 20)
})

function onInput() {
  showDropdown.value = true
}

function selectNode(node) {
  query.value = node.name
  showDropdown.value = false
  emit('select-node', node.uuid)
}

function selectFirst() {
  if (filteredNodes.value.length > 0) {
    selectNode(filteredNodes.value[0])
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/graph/GraphSearchBar.vue
git commit -m "feat: add GraphSearchBar with autocomplete"
```

---

## Task 9: Frontend — GraphLegend & GraphDetailPanel Components

**Files:**
- Create: `frontend/src/components/graph/GraphLegend.vue`
- Create: `frontend/src/components/graph/GraphDetailPanel.vue`

- [ ] **Step 1: Create the legend component**

Create `frontend/src/components/graph/GraphLegend.vue`:

```vue
<template>
  <div class="absolute bottom-3 left-3 z-10 bg-white border border-gray-200 rounded-lg shadow-sm p-3 max-w-xs">
    <div class="flex items-center justify-between mb-2">
      <h4 class="text-xs font-semibold text-red-500 uppercase tracking-wide">Entity Types</h4>
      <div class="flex gap-2">
        <button @click="$emit('show-all')" class="text-xs text-blue-600 hover:underline">All</button>
        <button @click="$emit('hide-all')" class="text-xs text-blue-600 hover:underline">None</button>
      </div>
    </div>
    <div class="flex flex-wrap gap-x-4 gap-y-1.5">
      <button
        v-for="et in entityTypes"
        :key="et.name"
        @click="$emit('toggle-type', et.name)"
        class="flex items-center gap-1.5 text-sm cursor-pointer"
        :class="hiddenTypes.has(et.name) ? 'opacity-30' : ''"
      >
        <span
          class="w-3 h-3 rounded-full flex-shrink-0"
          :style="{ backgroundColor: et.color }"
        />
        <span class="text-gray-700">{{ et.name }}</span>
        <span class="text-gray-400 text-xs">({{ et.count }})</span>
      </button>
    </div>
    <div v-if="filterBanner" class="mt-2 pt-2 border-t border-gray-100 text-xs text-gray-500">
      {{ filterBanner }}
      <button @click="$emit('show-all-nodes')" class="text-blue-600 hover:underline ml-1">Show all</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  entityTypes: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  filterBanner: { type: String, default: '' },
})

defineEmits(['toggle-type', 'show-all', 'hide-all', 'show-all-nodes'])
</script>
```

- [ ] **Step 2: Create the detail panel component**

Create `frontend/src/components/graph/GraphDetailPanel.vue`:

```vue
<template>
  <transition name="slide">
    <div
      v-if="node"
      class="absolute top-0 right-0 h-full w-80 bg-white border-l border-gray-200 shadow-lg z-20 overflow-y-auto"
    >
      <div class="p-4">
        <!-- Header -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-2">
            <span
              class="w-4 h-4 rounded-full flex-shrink-0"
              :style="{ backgroundColor: nodeColor }"
            />
            <h3 class="text-lg font-semibold text-gray-900">{{ node.name }}</h3>
          </div>
          <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 p-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Type badge -->
        <span
          class="inline-block px-2 py-0.5 rounded text-xs font-medium text-white mb-3"
          :style="{ backgroundColor: nodeColor }"
        >
          {{ node.entityType }}
        </span>

        <!-- Summary -->
        <div v-if="node.summary" class="mb-4">
          <p class="text-sm text-gray-600 leading-relaxed">{{ node.summary }}</p>
        </div>

        <!-- Relationships -->
        <div v-if="node.relationships && node.relationships.length > 0">
          <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Relationships ({{ node.relationships.length }})
          </h4>
          <div class="space-y-1.5">
            <button
              v-for="(rel, i) in node.relationships"
              :key="i"
              @click="$emit('navigate-to', rel.direction === 'outgoing' ? rel.targetId : rel.sourceId)"
              class="block w-full text-left text-sm text-gray-600 hover:text-indigo-600 hover:bg-indigo-50 rounded px-2 py-1.5 transition-colors"
            >
              <span class="text-gray-400">{{ rel.direction === 'outgoing' ? '→' : '←' }}</span>
              <span class="font-medium text-gray-500 mx-1">{{ rel.name }}</span>
              <span>{{ rel.direction === 'outgoing' ? rel.targetName : rel.sourceName }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { getEntityColor } from './graphColors.js'

const props = defineProps({
  node: { type: Object, default: null },
})

defineEmits(['close', 'navigate-to'])

const nodeColor = computed(() =>
  props.node ? getEntityColor(props.node.entityType) : '#999'
)
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add src/components/graph/GraphLegend.vue src/components/graph/GraphDetailPanel.vue
git commit -m "feat: add GraphLegend and GraphDetailPanel components"
```

---

## Task 10: Frontend — GraphVisualization Container

**Files:**
- Create: `frontend/src/components/graph/GraphVisualization.vue`

- [ ] **Step 1: Create the main orchestrator component**

Create `frontend/src/components/graph/GraphVisualization.vue`:

```vue
<template>
  <div
    ref="vizRef"
    class="relative bg-gray-50 rounded-lg border border-gray-200 overflow-hidden"
    :class="isFullscreen ? 'fixed inset-0 z-50 rounded-none' : 'h-full'"
  >
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center h-full text-gray-400">
      Loading graph...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center h-full text-red-500 text-sm">
      {{ error }}
    </div>

    <!-- Graph -->
    <template v-else>
      <GraphCanvas
        ref="canvasRef"
        :nodes="visibleNodes"
        :edges="edges"
        :hidden-types="hiddenTypes"
        :show-edge-labels="showEdgeLabels"
        :layout-name="layoutName"
        :selected-node-id="selectedNodeId"
        @node-click="onNodeClick"
        @node-hover="onNodeHover"
        @node-unhover="onNodeUnhover"
      />

      <GraphSearchBar
        :nodes="nodes"
        @select-node="onSearchSelect"
      />

      <GraphControls
        :show-edge-labels="showEdgeLabels"
        :layout-name="layoutName"
        :is-fullscreen="isFullscreen"
        @refresh="canvasRef?.runLayout()"
        @toggle-fullscreen="toggleFullscreen"
        @toggle-edge-labels="showEdgeLabels = !showEdgeLabels"
        @change-layout="layoutName = $event"
        @export="onExport"
      />

      <GraphLegend
        :entity-types="entityTypeSummary"
        :hidden-types="hiddenTypes"
        :filter-banner="filterBanner"
        @toggle-type="toggleType"
        @show-all="hiddenTypes.clear()"
        @hide-all="hideAllTypes"
        @show-all-nodes="showAllNodes"
      />

      <GraphDetailPanel
        :node="selectedNode"
        @close="selectedNode = null"
        @navigate-to="onNavigateTo"
      />

      <!-- Hover tooltip -->
      <div
        v-if="hoveredNode"
        class="absolute pointer-events-none bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg z-30 whitespace-nowrap"
        :style="{ left: hoveredNode.position.x + 12 + 'px', top: hoveredNode.position.y - 28 + 'px' }"
      >
        {{ hoveredNode.name }}
        <span class="text-gray-400 ml-1">{{ hoveredNode.entityType }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import GraphCanvas from './GraphCanvas.vue'
import GraphControls from './GraphControls.vue'
import GraphSearchBar from './GraphSearchBar.vue'
import GraphLegend from './GraphLegend.vue'
import GraphDetailPanel from './GraphDetailPanel.vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

const NODE_LIMIT = 50
const NODE_THRESHOLD = 100

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  metadata: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
})

const emit = defineEmits(['node-selected'])

const canvasRef = ref(null)
const vizRef = ref(null)

// State
const showEdgeLabels = ref(false)
const layoutName = ref('cose-bilkent')
const isFullscreen = ref(false)
const hiddenTypes = ref(new Set())
const selectedNode = ref(null)
const selectedNodeId = ref(null)
const hoveredNode = ref(null)
let hoverTimeout = null
const showAll = ref(false)

// Smart filtering
const visibleNodes = computed(() => {
  if (showAll.value || props.nodes.length <= NODE_THRESHOLD) return props.nodes
  return [...props.nodes]
    .sort((a, b) => b.connection_count - a.connection_count)
    .slice(0, NODE_LIMIT)
})

const filterBanner = computed(() => {
  if (showAll.value || props.nodes.length <= NODE_THRESHOLD) return ''
  return `Showing ${NODE_LIMIT} of ${props.nodes.length} nodes.`
})

// Entity type summary for legend
const entityTypeSummary = computed(() => {
  const counts = {}
  for (const node of props.nodes) {
    const type = getPrimaryLabel(node.labels)
    counts[type] = (counts[type] || 0) + 1
  }
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count, color: getEntityColor(name) }))
    .sort((a, b) => b.count - a.count)
})

// Actions
function toggleType(type) {
  const s = new Set(hiddenTypes.value)
  if (s.has(type)) s.delete(type)
  else s.add(type)
  hiddenTypes.value = s
}

function hideAllTypes() {
  hiddenTypes.value = new Set(entityTypeSummary.value.map((t) => t.name))
}

function showAllNodes() {
  showAll.value = true
}

function onNodeClick(data) {
  selectedNode.value = data
  selectedNodeId.value = data.id
  emit('node-selected', data.name)
}

function onNodeHover(data) {
  clearTimeout(hoverTimeout)
  hoverTimeout = setTimeout(() => {
    hoveredNode.value = data
  }, 200)
}

function onNodeUnhover() {
  clearTimeout(hoverTimeout)
  hoveredNode.value = null
}

function onSearchSelect(nodeId) {
  selectedNodeId.value = nodeId
  // Trigger a click-like data load for the detail panel
  const node = props.nodes.find((n) => n.uuid === nodeId)
  if (node) {
    // Let canvas handle the focus, but we need relationships from canvas
    canvasRef.value?.focusNode(nodeId)
  }
}

function onNavigateTo(nodeId) {
  selectedNodeId.value = nodeId
  canvasRef.value?.focusNode(nodeId)
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

function onExport(format) {
  if (!canvasRef.value) return
  const data = canvasRef.value.exportImage(format)
  if (!data) return

  if (format === 'svg') {
    const blob = new Blob([data], { type: 'image/svg+xml' })
    downloadBlob(blob, 'graph.svg')
  } else {
    // PNG comes as data URL
    const link = document.createElement('a')
    link.download = 'graph.png'
    link.href = data
    link.click()
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.download = filename
  link.href = url
  link.click()
  URL.revokeObjectURL(url)
}

function onEsc(e) {
  if (e.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
  }
}

onMounted(() => document.addEventListener('keydown', onEsc))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onEsc)
  clearTimeout(hoverTimeout)
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/graph/GraphVisualization.vue
git commit -m "feat: add GraphVisualization container component"
```

---

## Task 11: Frontend — ViewModeToggle Component

**Files:**
- Create: `frontend/src/components/ViewModeToggle.vue`

- [ ] **Step 1: Create the mode toggle component**

Create `frontend/src/components/ViewModeToggle.vue`:

```vue
<template>
  <div class="inline-flex bg-gray-100 rounded-lg p-0.5">
    <button
      v-for="mode in availableModes"
      :key="mode.value"
      @click="$emit('update:modelValue', mode.value)"
      class="px-4 py-1.5 text-sm font-medium rounded-md transition-colors"
      :class="modelValue === mode.value
        ? 'bg-white text-gray-900 shadow-sm'
        : 'text-gray-500 hover:text-gray-700'"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: 'report' },
  compact: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const allModes = [
  { value: 'graph', label: 'Graph' },
  { value: 'dual', label: 'Dual Column' },
  { value: 'report', label: 'Report' },
]

const availableModes = computed(() => {
  if (props.compact) return allModes.filter((m) => m.value !== 'dual')
  return allModes
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add src/components/ViewModeToggle.vue
git commit -m "feat: add ViewModeToggle component"
```

---

## Task 12: Frontend — Integrate into SimulationResults.vue

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Rewrite SimulationResults.vue with graph integration**

Replace the full contents of `frontend/src/views/SimulationResults.vue`:

```vue
<template>
  <div :class="viewMode === 'graph' || isGraphFullscreen ? '' : 'max-w-4xl mx-auto px-4 py-8'">
    <!-- Header -->
    <div v-if="!isGraphFullscreen" class="mb-6 flex items-center justify-between" :class="viewMode !== 'report' ? 'px-4 pt-8' : ''">
      <div>
        <router-link to="/dashboard" class="text-sm text-blue-600 hover:underline">&larr; Back to Dashboard</router-link>
        <h1 class="text-2xl font-bold text-gray-900 mt-2">Simulation Results</h1>
      </div>
      <div class="flex items-center gap-4">
        <ViewModeToggle
          v-if="job && hasGraph"
          v-model="viewMode"
          :compact="isSmallScreen"
        />
        <ExportButtons
          v-if="job"
          :job-id="jobId"
          :report-content="job.report"
          :messages="job.messages"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-gray-500">
      Loading results...
    </div>

    <div v-else-if="job">
      <!-- Job meta (hidden in fullscreen graph mode) -->
      <div v-if="viewMode === 'report' || viewMode === 'dual'" class="space-y-6" :class="viewMode === 'dual' ? 'px-4' : ''">
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-lg font-semibold text-gray-800 mb-1">{{ job.goal }}</h2>
          <p class="text-sm text-gray-500 capitalize">
            {{ job.tier }} tier &bull; Completed {{ formatDate(job.completed_at) }}
          </p>
        </div>
      </div>

      <!-- Graph Mode -->
      <div v-if="viewMode === 'graph'" class="px-4 mt-4" style="height: calc(100vh - 180px)">
        <GraphVisualization
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
          :loading="graphLoading"
          :error="graphError"
          @node-selected="onNodeSelected"
        />
      </div>

      <!-- Dual Column Mode -->
      <div v-else-if="viewMode === 'dual'" class="flex px-4 mt-4 gap-0" style="height: calc(100vh - 240px)">
        <div class="flex-1 min-w-[300px]" style="flex-basis: 50%">
          <GraphVisualization
            :nodes="graphData?.nodes || []"
            :edges="graphData?.edges || []"
            :metadata="graphData?.metadata || {}"
            :loading="graphLoading"
            :error="graphError"
            @node-selected="onNodeSelected"
          />
        </div>
        <div
          class="w-1 bg-gray-200 hover:bg-indigo-300 cursor-col-resize flex-shrink-0 transition-colors"
          @mousedown="startResize"
        />
        <div
          ref="reportPaneRef"
          class="flex-1 min-w-[300px] overflow-y-auto bg-white border border-gray-200 rounded-lg p-6"
          style="flex-basis: 50%"
        >
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Report</h3>
          <ReportViewer ref="reportViewerRef" :content="job.result_report || job.report || 'No report available.'" />
        </div>
      </div>

      <!-- Report Mode (original layout) -->
      <div v-else class="space-y-6 mt-6">
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Report</h3>
          <ReportViewer :content="job.result_report || job.report || 'No report available.'" />
        </div>

        <div v-if="chatMessages.length > 0" class="bg-white border border-gray-200 rounded-lg p-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-4">Agent Conversation</h3>
          <ChatReplay :messages="chatMessages" />
        </div>
      </div>
    </div>

    <div v-else class="text-center py-12 text-gray-500">
      Results not found.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ExportButtons from '../components/ExportButtons.vue'
import ViewModeToggle from '../components/ViewModeToggle.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import { getJob, getJobGraph } from '../api/jobs.js'

const route = useRoute()
const jobId = route.params.id

const job = ref(null)
const loading = ref(true)
const viewMode = ref('report')

// Graph state
const graphData = ref(null)
const graphLoading = ref(false)
const graphError = ref(null)
const hasGraph = ref(false)
const isGraphFullscreen = ref(false)

// Responsive
const isSmallScreen = ref(window.innerWidth < 768)
const reportPaneRef = ref(null)
const reportViewerRef = ref(null)

const chatMessages = computed(() => {
  if (!job.value) return []
  try {
    const raw = job.value.result_chat_log || job.value.chat_log || '[]'
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch { return [] }
})

// Fetch graph data lazily when switching to graph/dual mode
watch(viewMode, async (mode) => {
  if ((mode === 'graph' || mode === 'dual') && !graphData.value && !graphLoading.value) {
    await fetchGraphData()
  }
})

async function fetchGraphData() {
  graphLoading.value = true
  graphError.value = null
  try {
    graphData.value = await getJobGraph(jobId)
  } catch (err) {
    graphError.value = err.response?.status === 404
      ? 'Graph data not available for this simulation.'
      : 'Failed to load graph data.'
  } finally {
    graphLoading.value = false
  }
}

function onNodeSelected(entityName) {
  if (viewMode.value !== 'dual' || !reportPaneRef.value) return
  // Scroll report to first mention of the entity name
  const reportEl = reportPaneRef.value
  const walker = document.createTreeWalker(reportEl, NodeFilter.SHOW_TEXT)
  const lowerName = entityName.toLowerCase()
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.toLowerCase().includes(lowerName)) {
      walker.currentNode.parentElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Brief highlight
      const el = walker.currentNode.parentElement
      el.style.backgroundColor = 'rgba(99, 102, 241, 0.15)'
      setTimeout(() => { el.style.backgroundColor = '' }, 2000)
      break
    }
  }
}

// Resizable divider for dual column
let resizing = false
function startResize(e) {
  resizing = true
  const startX = e.clientX
  const container = e.target.parentElement
  const leftPane = container.children[0]
  const rightPane = container.children[2]
  const startLeftWidth = leftPane.getBoundingClientRect().width
  const totalWidth = container.getBoundingClientRect().width

  function onMove(ev) {
    if (!resizing) return
    const dx = ev.clientX - startX
    const newLeft = Math.max(300, Math.min(totalWidth - 304, startLeftWidth + dx))
    leftPane.style.flexBasis = newLeft + 'px'
    rightPane.style.flexBasis = (totalWidth - newLeft - 4) + 'px'
  }

  function onUp() {
    resizing = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
  if (isSmallScreen.value && viewMode.value === 'dual') {
    viewMode.value = 'graph'
  }
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    job.value = await getJob(jobId)
    // Check if graph data exists by attempting a lightweight check
    // We'll try to fetch graph and set hasGraph based on the response
    try {
      const gd = await getJobGraph(jobId)
      graphData.value = gd
      hasGraph.value = gd && gd.nodes && gd.nodes.length > 0
    } catch {
      hasGraph.value = false
    }
  } catch (err) {
    console.error('Failed to load results:', err)
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}
</script>
```

- [ ] **Step 2: Verify the app builds without errors**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/frontend
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add src/views/SimulationResults.vue
git commit -m "feat: integrate graph visualization into SimulationResults page"
```

---

## Task 13: Frontend — Add Graph to DemoResult.vue

**Files:**
- Modify: `frontend/src/views/DemoResult.vue`
- Modify: `frontend/src/api/demos.js`

- [ ] **Step 1: Update demos API to handle graph data**

The demo JSON files will need a `graph_data` field. Update `frontend/src/api/demos.js` — no code change needed since `getDemo()` returns the full JSON object. The demo JSON files just need to include `graph_data`.

- [ ] **Step 2: Add graph visualization to DemoResult.vue**

In `frontend/src/views/DemoResult.vue`, add the imports and graph integration. Replace the full file:

```vue
<template>
  <div :class="viewMode === 'graph' ? '' : 'max-w-4xl mx-auto px-4 py-10'">
    <!-- Loading state -->
    <div v-if="loading" class="text-center py-20 text-gray-400">
      Loading demo...
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="text-center py-20">
      <p class="text-red-500 text-lg mb-4">{{ error }}</p>
      <router-link to="/" class="text-blue-600 hover:underline">Back to home</router-link>
    </div>

    <!-- Demo content -->
    <div v-else-if="demo">
      <!-- Header -->
      <div class="mb-8" :class="viewMode !== 'report' ? 'px-4 pt-10' : ''">
        <div class="flex items-center gap-2 text-sm text-gray-400 mb-2">
          <router-link to="/" class="hover:text-blue-600">Home</router-link>
          <span>/</span>
          <span>Demo</span>
          <span>/</span>
          <span class="text-gray-600">{{ demo.title }}</span>
        </div>
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 mb-3">{{ demo.title }}</h1>
            <p class="text-gray-500 text-lg">{{ demo.description }}</p>
          </div>
          <ViewModeToggle
            v-if="hasGraph"
            v-model="viewMode"
            :compact="isSmallScreen"
          />
        </div>
        <div class="flex gap-4 mt-4 text-sm text-gray-400">
          <span v-if="demo.agent_count">{{ demo.agent_count.toLocaleString() }} agents</span>
          <span v-if="demo.rounds">·</span>
          <span v-if="demo.rounds">{{ demo.rounds }} rounds</span>
          <span v-if="demo.tier">·</span>
          <span v-if="demo.tier" class="capitalize">{{ demo.tier }} tier</span>
        </div>
      </div>

      <!-- Graph Mode -->
      <div v-if="viewMode === 'graph'" class="px-4" style="height: calc(100vh - 220px)">
        <GraphVisualization
          :nodes="graphData?.nodes || []"
          :edges="graphData?.edges || []"
          :metadata="graphData?.metadata || {}"
        />
      </div>

      <!-- Dual Column Mode -->
      <div v-else-if="viewMode === 'dual'" class="flex px-4 gap-0" style="height: calc(100vh - 280px)">
        <div class="flex-1 min-w-[300px]" style="flex-basis: 50%">
          <GraphVisualization
            :nodes="graphData?.nodes || []"
            :edges="graphData?.edges || []"
            :metadata="graphData?.metadata || {}"
            @node-selected="onNodeSelected"
          />
        </div>
        <div class="w-1 bg-gray-200 hover:bg-indigo-300 cursor-col-resize flex-shrink-0" />
        <div ref="reportPaneRef" class="flex-1 min-w-[300px] overflow-y-auto bg-white border border-gray-200 rounded-lg p-6" style="flex-basis: 50%">
          <ReportViewer :content="demo.report_markdown" />
        </div>
      </div>

      <!-- Report Mode (original layout) -->
      <template v-else>
        <!-- Seed Summary -->
        <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-5 mb-8">
          <h2 class="text-sm font-semibold text-yellow-700 uppercase tracking-wide mb-2">Seed Event</h2>
          <p class="text-gray-800">{{ demo.seed_summary }}</p>
        </div>

        <!-- Goal -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-5 mb-8">
          <h2 class="text-sm font-semibold text-blue-700 uppercase tracking-wide mb-2">Simulation Goal</h2>
          <p class="text-gray-800">{{ demo.goal }}</p>
        </div>

        <!-- Report -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-gray-900 mb-4">Simulation Report</h2>
          <div class="border border-gray-200 rounded-lg p-6 bg-white shadow-sm">
            <ReportViewer :content="demo.report_markdown" />
          </div>
        </div>

        <!-- Chat Replay -->
        <div class="mb-10">
          <h2 class="text-xl font-bold text-gray-900 mb-4">Agent Chat Log</h2>
          <ChatReplay :messages="chatMessages" />
        </div>

        <!-- CTA Banner -->
        <div class="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl p-8 text-center text-white">
          <h2 class="text-2xl font-bold mb-2">Run Your Own Simulation</h2>
          <p class="text-blue-100 mb-6">
            Upload any seed document and let FishCloud simulate public opinion, market reactions, or narrative evolution at scale.
          </p>
          <router-link
            to="/register"
            class="inline-block px-8 py-3 bg-white text-blue-600 font-semibold rounded-lg hover:bg-blue-50 transition-colors"
          >
            Get started free
          </router-link>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'
import ViewModeToggle from '../components/ViewModeToggle.vue'
import GraphVisualization from '../components/graph/GraphVisualization.vue'
import { getDemo } from '../api/demos.js'

const route = useRoute()
const demo = ref(null)
const loading = ref(true)
const error = ref(null)
const viewMode = ref('report')
const isSmallScreen = ref(window.innerWidth < 768)
const reportPaneRef = ref(null)

const chatMessages = computed(() => {
  if (!demo.value?.chat_log) return []
  return demo.value.chat_log.map((entry) => ({
    role: 'assistant',
    agent: entry.agent_name,
    content: entry.action_args?.content || JSON.stringify(entry.action_args),
    timestamp: null,
  }))
})

const graphData = computed(() => demo.value?.graph_data || null)
const hasGraph = computed(() => graphData.value && graphData.value.nodes && graphData.value.nodes.length > 0)

function onNodeSelected(entityName) {
  if (viewMode.value !== 'dual' || !reportPaneRef.value) return
  const walker = document.createTreeWalker(reportPaneRef.value, NodeFilter.SHOW_TEXT)
  const lowerName = entityName.toLowerCase()
  while (walker.nextNode()) {
    if (walker.currentNode.textContent.toLowerCase().includes(lowerName)) {
      walker.currentNode.parentElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const el = walker.currentNode.parentElement
      el.style.backgroundColor = 'rgba(99, 102, 241, 0.15)'
      setTimeout(() => { el.style.backgroundColor = '' }, 2000)
      break
    }
  }
}

function onResize() {
  isSmallScreen.value = window.innerWidth < 768
  if (isSmallScreen.value && viewMode.value === 'dual') viewMode.value = 'graph'
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    demo.value = await getDemo(route.params.slug)
  } catch (e) {
    error.value = e.message || 'Failed to load demo.'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>
```

- [ ] **Step 3: Commit**

```bash
git add src/views/DemoResult.vue
git commit -m "feat: add graph visualization to demo result page"
```

---

## Task 14: Build Verification & Final Commit

**Files:**
- All modified files

- [ ] **Step 1: Verify the frontend builds**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/frontend
npm run build
```

Expected: Build succeeds with no errors. Fix any import or syntax issues.

- [ ] **Step 2: Verify linting passes (if configured)**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/frontend
npm run lint 2>/dev/null || echo "No lint script configured"
```

- [ ] **Step 3: Manual smoke test checklist**

Start the dev server and verify:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat/frontend
npm run dev
```

Check:
- `/sim/:id/results` loads without errors in Report mode
- ViewModeToggle appears when graph data exists
- Graph mode renders Cytoscape canvas
- Dual Column mode shows graph + report side-by-side
- Node hover shows tooltip
- Node click opens detail panel
- Entity type legend shows colored dots
- Search autocomplete works
- Layout selector switches layouts
- Edge labels toggle works
- Export PNG/SVG downloads a file
- Fullscreen mode works and Esc exits it
- Responsive: on narrow viewport, dual column is hidden

- [ ] **Step 4: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address build and integration issues for graph visualization"
```
