# Graph Relationship Visualization for Reports

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Frontend graph visualization component + backend graph data persistence

## Overview

Add an interactive graph/network visualization to the simulation results page, showing entities (nodes) and their relationships (edges) extracted from the MiroFish simulation's Zep graph memory. Users can explore the knowledge graph alongside the markdown report in multiple view modes.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data source | Extract & persist from Zep before ephemeral graph is destroyed | Most reliable -- captures actual graph data at source |
| View modes | Full-screen graph + dual-column + report-only with toggle | Matches reference UI; best of both worlds |
| Library | Cytoscape.js with cose-bilkent layout extension | Purpose-built for graph viz, excellent force-directed layouts, Vue-compatible |
| Scale handling | Smart filtering -- top N nodes by connection count, entity type toggles | Avoids overwhelming the view while preserving user control |
| Interactions | Hover tooltip + click detail panel | Progressive disclosure at two levels |
| Controls | Full set -- legend/filter, zoom/pan, edge labels, refresh, fullscreen, search, node sizing, export, layout selector, edge thickness | Complete graph exploration toolkit |

## Backend: Graph Data Persistence & API

### Graph Snapshot

After MiroFish simulation completes (pipeline stage 4→5), before the ephemeral Zep graph is destroyed:

1. Run `panorama_search` to extract all nodes and edges
2. Serialize to JSON
3. Store in a new `result_graph` TEXT column on the `SimulationJob` model (same pattern as `result_report` and `result_chat_log`)

### New API Endpoint

```
GET /api/jobs/{job_id}/graph
→ 200: { nodes: [...], edges: [...], metadata: {...} }
→ 404: { detail: "Graph data not available" }
```

Separate from the main job endpoint to avoid bloating the job detail response.

### Node Schema

```json
{
  "uuid": "string",
  "name": "string",
  "labels": ["Person", "Professor"],
  "summary": "Brief description of the entity",
  "connection_count": 12
}
```

### Edge Schema

```json
{
  "uuid": "string",
  "name": "PARTICIPATES_IN_GOVERNANCE",
  "fact": "Professor Zhang participates in university governance",
  "source_node_uuid": "...",
  "target_node_uuid": "...",
  "source_node_name": "张教授",
  "target_node_name": "学校"
}
```

### Metadata Schema

```json
{
  "entity_types": ["Person", "University", "Organization"],
  "total_nodes": 247,
  "total_edges": 512
}
```

## Frontend: Component Architecture

### Component Tree

```
SimulationResults.vue (modified)
├── ViewModeToggle.vue          ← NEW: "Graph" | "Dual Column" | "Report" toggle
├── GraphVisualization.vue      ← NEW: main graph container
│   ├── GraphCanvas.vue         ← Cytoscape.js renderer
│   ├── GraphControls.vue       ← toolbar: search, layout selector, export, etc.
│   ├── GraphLegend.vue         ← entity type legend with filter toggles
│   ├── GraphDetailPanel.vue    ← right-side panel on node click
│   └── GraphSearchBar.vue      ← find node by name
├── ReportViewer.vue            (existing, unchanged)
├── ChatReplay.vue              (existing, unchanged)
└── ExportButtons.vue           (existing, unchanged)
```

### View Modes (SimulationResults.vue)

- **Graph mode:** `GraphVisualization` takes full width, report/chat hidden
- **Dual Column mode:** `GraphVisualization` on the left (50%), `ReportViewer` on the right (50%), resizable divider
- **Report mode:** Current view unchanged (report + chat + export)

### Data Flow

1. `SimulationResults.vue` fetches job data on mount (existing behavior)
2. When user switches to Graph or Dual Column mode, lazy-fetch graph data via `GET /api/jobs/{id}/graph`
3. Graph data passed as props to `GraphVisualization.vue`
4. `GraphVisualization` manages Cytoscape instance lifecycle, passes events up via emits

### New API Module Addition

```js
// src/api/jobs.js -- add:
export function getJobGraph(jobId) {
  return api.get(`/jobs/${jobId}/graph`)
}
```

## Graph Rendering & Styling

### Cytoscape.js Setup

- Force-directed layout using `cose-bilkent` extension (better clustering than default `cose`)
- Physics simulation runs on initial load, then settles
- User can drag nodes to reposition after settling
- Refresh button re-runs the layout algorithm

### Node Styling by Entity Type

| Entity Type | Color |
|---|---|
| University | `#f97316` (orange) |
| Entity | `#1e40af` (dark blue) |
| Alumni | `#991b1b` (dark red) |
| Organization | `#22c55e` (green) |
| Student | `#dc2626` (red) |
| Professor | `#ea580c` (burnt orange) |
| Person | `#3b82f6` (blue) |
| MediaOutlet | `#7c3aed` (purple) |
| LegalAuthority | `#16a34a` (emerald) |
| OpinionLeader | `#f59e0b` (amber) |
| GovernmentAgency | `#b91c1c` (crimson) |

- Dynamic color assignment for entity types not in the predefined map (hash entity type name to a color from a palette)
- Node size: base size + scaled by `connection_count` (more connections = larger node)
- Node label: entity `name` displayed below node

### Edge Styling

- Default: thin gray lines (`rgba(150,150,150,0.3)`)
- Edge labels: relationship `name` displayed along edge (togglable)
- On node hover: connected edges brighten, non-connected edges + nodes dim to 20% opacity
- Edge thickness: uniform (default) or scaled by number of edges between the same two nodes (multiple relationships between the same pair = thicker line)

### Layout Algorithms (selector)

- **Force-directed** (default) -- `cose-bilkent`
- **Circular** -- `circle`
- **Hierarchical** -- `dagre`
- **Grid** -- `grid`

## Controls & Interactions

### Toolbar (GraphControls.vue) -- top-right overlay

- **Refresh** -- re-runs current layout algorithm
- **Fullscreen** toggle -- expands to viewport, exit with Esc or toggle
- **Show Edge Labels** toggle -- default off for cleaner initial view
- **Layout selector** dropdown -- Force-directed / Circular / Hierarchical / Grid
- **Export** dropdown -- PNG, SVG via Cytoscape's `cy.png()` / `cy.svg()`

### Search (GraphSearchBar.vue) -- top-left overlay

- Text input with autocomplete listing node names
- On select: zooms to node, highlights it, opens detail panel
- Fuzzy matching for partial name input

### Legend (GraphLegend.vue) -- bottom-left overlay

- All entity types with colored dots
- Each type is a clickable toggle to hide/show nodes of that type
- Node count per type: `Person (24)`
- "Show All" / "Hide All" quick actions

### Detail Panel (GraphDetailPanel.vue) -- right side, slides in on click

- Entity name + colored type badge
- Summary text from node `summary` field
- Relationships list grouped by direction:
  - Outgoing: `→ RELATIONSHIP_NAME target_name`
  - Incoming: `← RELATIONSHIP_NAME source_name`
- Click a relationship to navigate to that connected node
- Close button (X) to dismiss

### Hover Tooltip

- Small floating label: `name` + `type`
- 200ms hover delay, disappears on mouseout
- Positioned above node

### Smart Filtering (initial load)

- If graph has >100 nodes, show top 50 by connection count
- Banner: "Showing 50 of 247 nodes. Show all"
- Entity type toggles work within filtered set
- "Show all" loads the complete graph

## Dual Column Mode

### Layout

- Left pane: `GraphVisualization` (canvas + controls)
- Right pane: `ReportViewer` (markdown, scrollable)
- Draggable divider, default 50/50 split
- Minimum pane width: 300px

### Cross-linking (graph ↔ report)

- Click a node in graph → report scrolls to first mention of entity name
- Highlighted mentions get subtle background color matching entity type
- Best-effort name matching (no structured links)

### Responsive Behavior

- Screens < 768px: dual column disabled, toggle shows only "Graph" and "Report"
- Graph controls reflow to compact layout on smaller viewports

## Dependencies

### New npm packages

- `cytoscape` -- core graph rendering
- `cytoscape-cose-bilkent` -- force-directed layout extension
- `cytoscape-dagre` -- hierarchical layout extension

### Backend changes

- New `result_graph` column on `SimulationJob` model
- New `GET /api/jobs/{id}/graph` endpoint
- Graph extraction step in pipeline result processing (before Zep teardown)
- Alembic migration for the new column

## Demo Pages

- `DemoResult.vue` gets the same graph visualization
- Demo data includes pre-extracted graph JSON
- Same component reuse: `GraphVisualization.vue` works for both authenticated results and public demos
