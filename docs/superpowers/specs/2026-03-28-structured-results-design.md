# Structured Results & Graph Detail Panel — Design Spec

**Date:** March 28, 2026
**GitHub Issue:** #11
**Goal:** Make the Story tab show structured visual components (findings, sentiment, coalitions, confidence) instead of raw markdown, and make the Graph tab detail panel show node relationships and properties.

---

## 1. Architecture

Two independent workstreams sharing a common backend change:

**Story Tab:** Add `result_structured` JSON column to SimulationJob. Populate it on the GPU pod from data already available (outline.json, agent actions, graph data). Frontend Story view renders FindingCards, SentimentBars, CoalitionCards, ConfidenceGrid from this JSON.

**Graph Tab:** Build node relationships from edge data on the frontend (no backend change needed). Expand entity type color mapping. Show node properties in detail panel.

No extra LLM calls. All structured data is derived from existing pipeline outputs.

---

## 2. Story Tab — Structured Results

### 2.1 Data Shape (`result_structured` JSON)

```json
{
  "brief": "2-3 paragraph executive summary from outline.json",
  "findings": [
    {
      "label": "FINDING",
      "title": "Section title from outline",
      "description": "First paragraph of the section content",
      "metric": "",
      "accentColor": "#22D3EE"
    }
  ],
  "sentiment": [
    {
      "label": "Agent cluster or platform name",
      "value": 72,
      "direction": "positive"
    }
  ],
  "coalitions": [
    {
      "name": "Coalition name",
      "description": "How these agents relate",
      "agents": 5,
      "strength": 85,
      "color": "#22D3EE"
    }
  ],
  "confidence": [
    { "label": "Agents", "value": "24", "color": "#22D3EE" },
    { "label": "Rounds", "value": "72", "color": "#A78BFA" },
    { "label": "Graph Entities", "value": "48", "color": "#6EE7B7" }
  ]
}
```

### 2.2 Data Sources (no LLM needed)

| Field | Source | Method |
|-------|--------|--------|
| `brief` | `outline.json` → `summary` field | Direct read from pod filesystem |
| `findings` | `outline.json` → sections[] + `section_*.md` files | Section title + first paragraph as description |
| `sentiment` | Agent actions from chat_log | Count action types per platform: CREATE_POST and LIKE = positive engagement, grouped by platform (twitter/reddit) |
| `coalitions` | Agent actions (FOLLOW, REPOST patterns) | Group agents by mutual follow/repost behavior. Strength = shared action % |
| `confidence` | Simulation metadata | Total agents, rounds completed, graph node/edge count, action count |

### 2.3 Accent Colors for Findings

Cycle through the palette based on section index:
```python
FINDING_COLORS = ["#22D3EE", "#A78BFA", "#F97316", "#6EE7B7", "#FF6B6B", "#FBBF24"]
```

### 2.4 Where Extraction Happens

In `infra/docker/run_job.py`, after `generate_report()` and `collect_chat_log()`, add a new `build_structured_results()` step that:

1. Reads `outline.json` from the report directory (already on disk)
2. Reads `section_*.md` files (already on disk)
3. Analyzes the chat_log list (already in memory)
4. Reads graph_data (already extracted)
5. Returns a dict matching the schema above

This dict is serialized as JSON and returned alongside report, chat_log, and graph_data in the pipeline result.

### 2.5 Backend Changes

- Add `result_structured` column (Text, nullable) to SimulationJob
- Add `result_structured` to JobResponse schema
- `_save_job_results` in persistence.py stores the new field
- Alembic migration for the column
- `run_job.py` builds and writes `structured_results.json` to output dir

### 2.6 Frontend Changes

In `SimulationResults.vue` Story view:
- If `job.result_structured` is present, parse it and render:
  - Executive brief at top (styled paragraph)
  - ConfidenceGrid (simulation stats)
  - FindingCards (one per section)
  - SentimentBars (platform engagement)
  - CoalitionCards (if coalitions detected)
- If `result_structured` is null, fall back to rendering report markdown (backward compat)

---

## 3. Graph Tab — Detail Panel & Entity Types

### 3.1 Build Node Relationships on Frontend

When `SimulationResults.vue` receives graph data, build a `relationships` array for each node from the edges:

```javascript
function buildNodeRelationships(nodes, edges) {
  const relMap = {}  // nodeUUID → relationships[]
  for (const edge of edges) {
    // Outgoing from source
    if (!relMap[edge.source_node_uuid]) relMap[edge.source_node_uuid] = []
    relMap[edge.source_node_uuid].push({
      direction: 'outgoing',
      type: edge.name,
      target_uuid: edge.target_node_uuid,
      targetName: edge.target_node_name,
      fact: edge.fact,
    })
    // Incoming to target
    if (!relMap[edge.target_node_uuid]) relMap[edge.target_node_uuid] = []
    relMap[edge.target_node_uuid].push({
      direction: 'incoming',
      type: edge.name,
      source_uuid: edge.source_node_uuid,
      sourceName: edge.source_node_name,
      fact: edge.fact,
    })
  }
  // Attach to nodes
  return nodes.map(n => ({
    ...n,
    relationships: relMap[n.uuid] || [],
  }))
}
```

This is called once when graph data loads. The detail panel already reads `node.relationships` — it just needs data.

### 3.2 Expand Entity Type Colors

Update `graphColors.js` to cover all types Zep produces:

```javascript
const ENTITY_TYPE_COLORS = {
  // People
  Person: '#A78BFA',
  PoliticalFigure: '#A78BFA',
  PrimeMinister: '#A78BFA',
  GovernmentOfficial: '#A78BFA',
  JudicialFigure: '#818CF8',
  OppositionLeader: '#FB923C',

  // Organizations
  Organization: '#22D3EE',
  GovernmentAgency: '#FF6B6B',
  InternationalOrganization: '#14B8A6',
  RegulatoryAgency: '#10B981',

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

  // Academics
  University: '#F97316',
  Professor: '#F97316',
  Student: '#FF6B6B',
  Alumni: '#FF6B6B',

  // Generic
  Entity: '#6B7280',
}
```

### 3.3 Node Properties in Detail Panel

The detail panel currently shows name, type badge, and summary. Add a **Properties** section that parses structured data from the node summary or labels:

```vue
<!-- Properties section in GraphDetailPanel.vue -->
<div v-if="nodeProperties.length > 0" class="mb-4">
  <h4 class="text-[10px] font-bold tracking-wider text-mist-slate uppercase mb-2">Properties</h4>
  <div v-for="prop in nodeProperties" :key="prop.key" class="flex justify-between text-xs py-0.5">
    <span class="text-mist-slate">{{ prop.key }}</span>
    <span class="text-mist-drift">{{ prop.value }}</span>
  </div>
</div>
```

Properties derived from available data:
- `type` — primary label
- `connections` — connection_count
- `labels` — all labels joined

---

## 4. Backward Compatibility

- Jobs completed before this change have `result_structured = null` — Story view falls back to markdown
- Graph detail panel works with existing data (just adds relationship building from edges)
- No migration of existing data required

---

## 5. Testing

### Backend
- `test_structured_results.py` — test `build_structured_results()` with sample outline.json + chat_log + graph_data
- Test that `result_structured` is included in JobResponse
- Test backward compat: old jobs without result_structured return null

### Frontend
- Verify Story view renders structured components when data present
- Verify Story view falls back to markdown when data absent
- Verify graph detail panel shows relationships from edges
