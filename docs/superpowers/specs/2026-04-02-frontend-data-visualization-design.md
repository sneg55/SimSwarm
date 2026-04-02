# Frontend Data Visualization

**Date:** 2026-04-02
**Status:** Approved

## Problem

SimSwarm's simulation engine produces rich per-agent data (posts, trades, market prices, social graph, sentiment trajectories) that is now extracted and stored in MinIO. But the frontend has no way to display it. The result pages look like ChatGPT output — a markdown report and a thin chat replay. The data that makes SimSwarm unique is invisible to users.

## Solution

Add a "Data" tab to the simulation results page with a dashboard of 7 visualization components, plus 2 compact chart cards inline in the Story view. All charts are custom SVG/Canvas — no charting library. Data is lazy-loaded from MinIO via presigned URLs.

## UI Placement (Hybrid)

- **Story view:** Two compact cards (market curve sparkline + engagement sparkline) appear inline alongside existing FindingCards and SentimentBars. Only shown when `sim_data_available` is true.
- **Data tab:** New 4th view mode (Story | Graph | Data | Report). Full dashboard with all 7 components in a 2-column responsive grid. Only shown when `sim_data_available` is true.

## Components

### Data tab — full-size (in `frontend/src/components/data/`)

| Component | Renders | Data file | Tech |
|-----------|---------|-----------|------|
| `MarketCurveChart.vue` | Green/red YES/NO probability lines with area fill, hover tooltip, axis labels | `market_curves.json` | SVG |
| `AgentTrajectoryChart.vue` | Multi-line sentiment over round windows, one line per agent, color by entity type | `agent_trajectories.json` | SVG |
| `EngagementChart.vue` | Stacked bar chart — posts/likes/comments per round window | `engagement_summary.json` | SVG |
| `TopPostsFeed.vue` | Scrollable list of top 50 posts with agent name, platform icon, content, engagement counts | `top_posts.json` | HTML/Tailwind |
| `SocialGraphView.vue` | Force-directed follow graph with mutual-follow highlights, node sizing by follower count | `social_graph.json` | Canvas |
| `TradeFeed.vue` | Chronological trade list — agent name, side (buy/sell), outcome, price, cost | `trades.json` | HTML/Tailwind |
| `AgentProfileCards.vue` | Grid of agent cards with bio, stance, influence weight, platform presence | `profiles.json` | HTML/Tailwind |

### Story view — compact cards (in `frontend/src/components/results/`)

| Component | Renders |
|-----------|---------|
| `MarketCurveCompact.vue` | Small market curve — just YES/NO lines + current price label, no axes/tooltips |
| `EngagementCompact.vue` | Small bar sparkline showing activity peaks per round window |

### Container

| Component | Purpose |
|-----------|---------|
| `DataDashboard.vue` | Dashboard grid layout (2-col responsive), fetches presigned URLs from `GET /api/jobs/{id}/sim-data`, lazy-loads JSON files via IntersectionObserver, passes data as props to children |

## Data Flow

```
SimulationResults.vue
  ├── viewMode = "story" → Story view
  │     ├── existing components (FindingCard, SentimentBars, etc.)
  │     ├── MarketCurveCompact (if sim_data_available)
  │     └── EngagementCompact (if sim_data_available)
  │
  ├── viewMode = "graph" → GraphVisualization (unchanged)
  │
  ├── viewMode = "report" → Report view (unchanged)
  │
  └── viewMode = "data" → DataDashboard (new, if sim_data_available)
        ├── GET /api/jobs/{id}/sim-data → { files: { filename: presigned_url } }
        ├── lazy-fetch each JSON file on scroll (IntersectionObserver)
        └── pass data as props to 7 child components
```

- "Data" tab only appears when `sim_data_available` is true on the job
- DataDashboard fetches presigned URLs once, lazy-loads individual JSON files as user scrolls
- Market curves and engagement load immediately (above the fold)
- Top posts, social graph, trades, profiles load when scrolled into view
- Compact Story cards share cached data if Data tab was already visited

## Chart Design

### Market Curve
- Green solid line (#4ADE80) = YES probability
- Red dashed line (#F87171) = NO probability
- Green area fill under YES line (15% opacity)
- X axis: trade index, Y axis: 0-100%
- Hover tooltip: trade #, YES %, NO %, cumulative volume
- Grid lines at 25%, 50%, 75%

### Agent Trajectories
- One line per agent, colored by entity type (using existing graphColors.js palette)
- X axis: round windows (0, 20, 40, ...), Y axis: sentiment (-1 to +1)
- Hover tooltip: agent name, round, sentiment score, post count
- Legend with agent names (toggleable)

### Engagement Chart
- Stacked vertical bars per round window
- Colors: posts (#22D3EE), likes (#6EE7B7), comments (#A78BFA)
- X axis: round windows, Y axis: count
- Hover tooltip: round, breakdown by type

### Social Graph
- Canvas-based force-directed layout (same pattern as GraphCanvas.vue)
- Nodes = agents, sized by follower count
- Edges = follow relationships
- Mutual follows highlighted with thicker/brighter edges
- Node colors by entity type

## Modified Existing Files

- `frontend/src/views/SimulationResults.vue` — add "data" viewMode, show DataDashboard, add compact cards to Story
- `frontend/src/components/ViewModeToggle.vue` — add "Data" option, conditionally shown
- `frontend/src/api/jobs.js` — add `getSimData(jobId)` function
- `frontend/src/composables/useSimulationData.js` — add sim data fetching/caching logic

## Design System

All components use the existing Tailwind theme:
- Backgrounds: ocean-abyss (#0B1426), ocean-deep (#0F2035)
- Borders: mist-depth (#1E293B)
- Text: mist-foam (#F1F5F9), mist-drift (#94A3B8), mist-slate (#64748B)
- Chart colors: ocean-cyan (#22D3EE), organic-seafoam (#6EE7B7), organic-violet (#A78BFA), coral (#FF6B6B)
- Market specific: green (#4ADE80) for YES, red (#F87171) for NO
- Border radius: 12-16px (rounded-xl/2xl)
- Font: Inter for labels, JetBrains Mono for numbers

## Scope Boundaries

**In scope:**
- 7 full-size data components + 2 compact Story cards + 1 dashboard container
- DataDashboard grid layout (2-column responsive)
- ViewModeToggle update (4th "Data" option, conditional)
- Lazy-loading JSON from presigned MinIO URLs
- SVG charts with hover tooltips
- Canvas social graph (reuse GraphCanvas pattern)
- HTML/Tailwind feeds and cards

**Out of scope:**
- Filtering/search within data views
- Exporting data views as images/CSV
- Real-time updates during simulation
- Mobile-optimized layouts (responsive collapse to single column is fine)
- Agent profile drill-down pages
