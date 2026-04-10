# Tooltip Explanations for Simulation Results

**Date:** 2026-04-10
**Status:** Approved

## Overview

Add hover tooltips to every visible data point, metric, and number across all three simulation results views (Story, Data, Graph). Each tooltip explains what the metric means and how it's calculated, written for non-technical domain experts.

## Decisions

- **Scope:** All ~40 metrics across ~25 components in Story, Data, and Graph views
- **Copy depth:** Both meaning ("what does this tell me?") and calculation ("where does this number come from?")
- **Trigger:** Hybrid — hovering the metric shows the tooltip; a subtle `ⓘ` icon provides a visual hint
- **Visual style:** Dark glass — `rgba(10,20,30,0.92)` background, teal border glow, matching the ocean/bioluminescent aesthetic
- **Architecture:** Custom `<InfoTooltip>` Vue 3 component + central `tooltipCopy.js` dictionary organized by component
- **Approach:** Custom component (no library dependency), ~150-200 lines

---

## Section 1: `<InfoTooltip>` Component

**File:** `frontend/src/components/InfoTooltip.vue`

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `copyKey` | String | required | Dot-path into dictionary, e.g. `"confidenceGrid.agentsActive"` |
| `position` | String | `"top"` | Preferred placement: `top`, `bottom`, `left`, `right`. Auto-flips if clipped. |
| `iconSize` | String | `"sm"` | Icon size: `sm` (12px) or `md` (16px) |

### Slot

Default slot wraps the metric being annotated:

```vue
<InfoTooltip copyKey="confidenceGrid.agentsActive">
  <span class="text-3xl font-bold">{{ animatedValue }}</span>
</InfoTooltip>
```

### Behavior

- Hover on slot content OR `ⓘ` icon shows tooltip after 200ms delay
- Mouse leave hides after 150ms grace period (cursor can move to tooltip itself)
- Mobile: first tap opens, tap outside dismisses, only one open at a time
- Viewport-aware: flips to opposite side if preferred position clips
- `ⓘ` icon: `inline-flex`, right of slot content, vertically centered, `text-teal-500/40`, brightens on hover

### Tooltip Panel Rendering

- Background: `bg-[rgba(10,20,30,0.92)]`
- Border: `border border-teal-500/20`
- Shape: `rounded-lg`
- Shadow: `shadow-lg shadow-teal-900/30`
- Max width: 280px
- **Title**: `text-teal-300 text-xs font-semibold uppercase tracking-wider`
- **Meaning**: `text-gray-200 text-sm leading-relaxed`
- Divider: `border-t border-teal-500/10`
- **Calculation**: `text-gray-400 text-xs leading-relaxed`, prefixed with "Calculated from:" in `text-teal-400/60`
- Animation: `opacity 0→1` + `translateY(4px→0)` over 150ms ease-out
- Arrow: 6px caret pointing toward trigger, matching background color

---

## Section 2: Tooltip Copy Dictionary

**File:** `frontend/src/data/tooltipCopy.js`

### Structure

```js
export const tooltipCopy = {
  'componentName.metricName': {
    title: 'Metric Name',
    meaning: 'What this tells you.',
    calculation: 'Where this number comes from.',
  },
}
```

### Naming Convention

`camelCaseComponentName.camelCaseMetricName`

### Copy Guidelines

- **title**: 2-4 words, plain-English metric name
- **meaning**: 1-2 sentences, answers "what does this tell me?", no jargon, active voice, present tense
- **calculation**: 1-2 sentences, answers "where does this number come from?", describes the process not the math

### Fallback Behavior

No match in dictionary: render slot content without icon or tooltip. Console warn in dev only.

### Dynamic Key Normalization

For components with backend-driven labels (ConfidenceGrid, SentimentBars), the component normalizes the label to a camelCase key at lookup time. A `normalizeKey` utility in `tooltipCopy.js` converts `"Agents Active"` → `agentsActive`. Logic: lowercase first char, strip spaces and capitalize each subsequent word's first letter (basic camelCase). Exported so components can import it.

### Full Copy

#### Story View

**ConfidenceGrid:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `confidenceGrid.agentsActive` | Agents Active | The number of simulated agents that participated in this scenario. Each agent has its own personality, knowledge, and goals. | Counted from the total agents that posted, traded, or interacted at least once during the simulation. |
| `confidenceGrid.roundsCompleted` | Rounds Completed | How many cycles the simulation ran. Each round represents a period where all agents can act — post, trade, react, and update their beliefs. | One round completes when every active agent has had a chance to act. The number depends on the tier and complexity of your scenario. |
| `confidenceGrid.totalInteractions` | Total Interactions | The combined number of actions agents took — posts, likes, comments, trades, and follows. Higher numbers mean a more active simulated community. | Sum of every discrete action across all agents and all rounds. |

**SentimentBars:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `sentimentBars.overallSentiment` | Overall Sentiment | The general emotional tone across all agents by the end of the simulation. Positive means the community leaned favorable; negative means skeptical or opposed. | Averaged from each agent's final sentiment score, which updates every round based on what they read, post, and experience. |
| `sentimentBars.consensus` | Consensus | How much agents agreed with each other by the end. High consensus means a dominant shared view emerged; low means opinions stayed divided. | Measured from the spread of final agent positions — tighter clustering means higher consensus. |
| `sentimentBars.volatility` | Volatility | How much opinions shifted during the simulation. High volatility means agents frequently changed their minds; low means positions were stable early. | Tracked from round-to-round sentiment changes across all agents, then averaged. |
| `sentimentBars.engagement` | Engagement | How actively agents participated relative to opportunities. High engagement means agents chose to post and interact rather than stay silent. | Ratio of actions agents actually took versus the maximum possible actions across all rounds. |

**CoalitionCard:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `coalitionCard.agents` | Coalition Members | How many agents belong to this group. Coalitions form naturally when agents with similar views start interacting and reinforcing each other. | Counted from agents the simulation identified as behaviorally clustered — they share stances, interact frequently, and reference similar ideas. |
| `coalitionCard.strength` | Coalition Strength | How tightly aligned this group is. A high percentage means members consistently agree with each other and act in coordination. | Measured from how often coalition members take the same stance and interact with each other versus with outsiders, across all rounds. |

**FindingCard:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `findingCard.metric` | Finding Metric | A standout number that captures the scale or impact of this finding. | Derived from the specific pattern described — may reflect engagement multiples, sentiment shifts, or adoption rates depending on the finding. |

**EngagementCompact:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `engagementCompact.totalPosts` | Total Posts | The total number of original posts agents published across all rounds. Posts are how agents share their views and influence others. | Sum of all CREATE_POST actions by every agent across every round. |
| `engagementCompact.totalLikes` | Total Likes | How many times agents endorsed each other's content. Likes signal agreement and amplify a post's reach within the simulation. | Sum of all LIKE_POST actions across every agent and round. |

**MarketCurveCompact:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `marketCurveCompact.currentYes` | Current YES Probability | The market's latest estimate that the predicted outcome will happen. Think of it like a crowd-sourced confidence level — agents bet real simulation credits on what they believe. | Derived from the last trade price. When agents buy YES shares, the price rises; when they sell, it falls. The percentage reflects the balance of conviction. |

**SimulationResults header:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `simulationResults.tier` | Simulation Tier | The complexity level of this run. Higher tiers use more agents, more rounds, and more capable AI models — producing richer and more nuanced results. | Set when the simulation was created. Each tier defines agent count, round count, context window, and GPU allocation. |
| `simulationResults.startedAt` | Started | When the simulation began processing on the GPU. | Recorded when the job was picked up by a GPU worker. |
| `simulationResults.completedAt` | Completed | When the simulation finished and results became available. | Recorded when the final round completes and all data is extracted and stored. |

#### Data View

**MarketCurveChart (canvas hover):**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `marketCurveChart.currentPrice` | Current Price | The latest market probability for this outcome. | Last trade price in the market's order book. |
| `marketCurveChart.tooltipYes` | YES Price | What the market thinks is the probability this outcome happens. | Set by the last trade — when an agent buys YES shares, the price moves up. |
| `marketCurveChart.tooltipNo` | NO Price | The implied probability this outcome does not happen. | Calculated as 100% minus the YES price. Always moves inversely. |
| `marketCurveChart.tooltipVolume` | Trade Volume | Total simulation currency spent on this trade. Larger trades signal stronger conviction from the agent. | The dollar cost the agent paid for the shares in this transaction. |

**EngagementChart (canvas hover):**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `engagementChart.posts` | Posts This Round | Original content published by agents during this round. | Count of CREATE_POST actions in this specific round. |
| `engagementChart.likes` | Likes This Round | Endorsements agents gave to each other's content this round. | Count of LIKE_POST and LIKE_COMMENT actions in this round. |
| `engagementChart.comments` | Comments This Round | Replies and reactions agents wrote on each other's posts. | Count of CREATE_COMMENT actions in this round. |
| `engagementChart.activeAgents` | Active Agents | How many agents did something this round — posted, liked, commented, or traded. Idle agents stayed quiet. | Count of distinct agents with at least one action in this round. |

**AgentTrajectoryChart (canvas hover):**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `agentTrajectoryChart.sentiment` | Agent Sentiment | This agent's emotional position at this point in the simulation. +1 is fully supportive, -1 is fully opposed, 0 is neutral. | Updated each round based on what the agent posted, read, and how others responded to them. Reflects cumulative belief evolution. |

**TopPostsFeed:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `topPostsFeed.likes` | Likes | How many other agents endorsed this post. Popular posts shape the conversation and pull sentiment toward them. | Count of LIKE_POST actions targeting this specific post. |
| `topPostsFeed.shares` | Shares | How many agents amplified this post to their followers. Shares extend a post's reach beyond the original audience. | Count of REPOST and QUOTE_POST actions targeting this post. |
| `topPostsFeed.dislikes` | Dislikes | How many agents actively disagreed with this post. Dislikes signal opposition and can dampen a post's influence. | Count of DISLIKE_POST actions targeting this post. |

**TradeFeed:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `tradeFeed.price` | Trade Price | The probability level at which this agent bought or sold. A BUY at 70% means the agent believes there's at least a 70% chance the outcome happens. | The market price at the moment this trade executed. |
| `tradeFeed.cost` | Trade Cost | How much simulation currency the agent spent on this position. Larger bets mean the agent had stronger conviction. | Calculated from share quantity multiplied by price. Reflects the agent's resource commitment. |

**AgentProfileCards:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `agentProfileCards.mbti` | Personality Type | The agent's simulated personality using the MBTI framework. This shapes how the agent processes information, makes decisions, and interacts with others. | Assigned during agent creation based on the persona configuration. Influences posting style, risk tolerance, and social behavior. |

**SocialGraphView (legend):**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `socialGraphView.nodeSize` | Node Size | Larger nodes represent agents with more followers. These agents have more social influence in the simulation. | Scaled from each agent's follower count using a square root scale for readability. |
| `socialGraphView.mutualEdge` | Bright Edges | A bright connection means both agents follow each other — a mutual relationship. These tend to be the strongest influence channels. | Detected when agent A follows agent B and agent B follows agent A. |

#### Graph View

**GraphLegend:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `graphLegend.entityCount` | Entity Count | How many knowledge graph nodes belong to this type. The graph captures people, organizations, concepts, and events the simulation discovered. | Counted from all nodes extracted from agent conversations and enrichment data, filtered by this entity type. |
| `graphLegend.sentimentPositive` | Positive Sentiment | Nodes the simulation community viewed favorably — they were discussed in supportive or optimistic terms. | Nodes with a final averaged sentiment score above +0.2. |
| `graphLegend.sentimentNegative` | Negative Sentiment | Nodes the community viewed unfavorably — discussed with skepticism, criticism, or opposition. | Nodes with a final averaged sentiment score below -0.2. |
| `graphLegend.sentimentNeutral` | Neutral Sentiment | Nodes discussed without strong positive or negative feeling — factual references or divided opinions that balanced out. | Nodes with a final averaged sentiment score between -0.2 and +0.2. |

**GraphDetailPanel:**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `graphDetailPanel.connectionCount` | Connections | How many other entities in the knowledge graph are linked to this one. More connections means this entity was referenced in more contexts. | Count of all incoming and outgoing relationships for this node. |
| `graphDetailPanel.sentiment` | Sentiment | The community's overall feeling toward this entity. Positive values mean favorable discussion; negative means critical or opposed. | Averaged from sentiment scores across all agent mentions and interactions involving this entity. |
| `graphDetailPanel.stance` | Stance | The dominant community position on this entity — supportive, opposing, or observer. | Derived from the balance of positive vs negative interactions. Supportive if sentiment > +0.2, opposing if < -0.2, observer otherwise. |
| `graphDetailPanel.influenceWeight` | Influence Weight | How much this entity affected the simulation's narrative. Higher multipliers mean this entity was central to how opinions formed and spread. | Calculated from connection count, mention frequency, and the sentiment intensity of interactions involving this entity. |
| `graphDetailPanel.roundNumber` | Round | Which simulation cycle this activity happened in. Earlier rounds show initial reactions; later rounds show evolved positions. | The sequential round number when this specific action was recorded. |

**GraphVisualization (hover tooltip):**

| Key | Title | Meaning | Calculation |
|-----|-------|---------|-------------|
| `graphVisualization.hoverSentiment` | Sentiment | How the simulated community feels about this entity. | Averaged from all agent mentions — positive means supportive discussion, negative means critical. |
| `graphVisualization.hoverStance` | Stance | The community's dominant position toward this entity. | Classified from the sentiment score — supportive, opposing, or neutral observer. |

---

## Section 3: Canvas Tooltip Integration

Canvas-rendered components (`GraphCanvas`, `SocialGraphView`, `AgentTrajectoryChart`, `MarketCurveChart`, `EngagementChart`) cannot use `<InfoTooltip>` on individual data points.

### Layer 1: Static DOM Labels

For titles, legends, axis labels, and headings rendered as DOM elements around the canvas, use `<InfoTooltip>` normally. Covers:
- Chart titles
- GraphLegend entity counts and sentiment counts
- GraphDetailPanel properties
- Axis labels where they exist as DOM text

### Layer 2: Enhance Existing Canvas Hover Tooltips

Extend existing `mousemove` hover tooltips with a meaning line from the dictionary:
- Append meaning text below existing data values
- Thin teal divider between data and meaning
- Match dark-glass styling for consistency
- Meaning only — no calculation line (keep hover tooltips fast/scannable)
- No `ⓘ` icon on canvas data points

**Example — MarketCurveChart hover, before:**
```
Trade #42
YES: 67%    NO: 33%
Vol: $150
```

**After:**
```
Trade #42
YES: 67%    NO: 33%
Vol: $150
─────────────────────
Each trade shifts the price based on
how much an agent is willing to pay
for their predicted outcome.
```

---

## Section 4: Mobile and Accessibility

### Mobile (Touch)

- `<InfoTooltip>`: first tap opens, tap outside dismisses, one tooltip open at a time
- Canvas hover tooltips: existing `touchstart`/`touchmove` handlers carry the added meaning line

### Keyboard

- `ⓘ` icon: `tabindex="0"`, `role="button"`, `aria-label="More info"`
- `Enter`/`Space` toggles tooltip open/closed
- `Escape` dismisses any open tooltip

### ARIA

- Tooltip panel: `role="tooltip"`, linked via `aria-describedby`
- `ⓘ` icon uses `aria-label` (not visible text)

### Reduced Motion

- Entry animation wrapped in `@media (prefers-reduced-motion: reduce)` — instant appearance, no transition

---

## Section 5: Integration Pattern Per Component

### Type 1: Simple DOM Metrics

Wrap metric element with `<InfoTooltip>`:
```vue
<InfoTooltip copyKey="coalitionCard.agents">
  <span class="text-sm">{{ agents }} agents</span>
</InfoTooltip>
```
**Applies to:** CoalitionCard, FindingCard, ConfidenceGrid, EngagementCompact, MarketCurveCompact, SimulationResults header.

### Type 2: Dynamic Label Items

Compute `copyKey` from the item's label:
```vue
<InfoTooltip :copyKey="`sentimentBars.${normalizeKey(bar.label)}`">
  <span>{{ bar.value }}</span>
</InfoTooltip>
```
**Applies to:** SentimentBars, ConfidenceGrid.

### Type 3: DOM Legends Around Canvases

Same as Type 1, applied to legend and detail panel elements.
**Applies to:** GraphLegend, GraphDetailPanel, chart titles.

### Type 4: Canvas Hover Tooltip Enhancement

Edit existing tooltip rendering functions to append meaning line with divider.
**Applies to:** MarketCurveChart, EngagementChart, AgentTrajectoryChart, GraphVisualization.

### Type 5: Feed Item Metrics

Wrap individual engagement numbers:
```vue
<InfoTooltip copyKey="topPostsFeed.likes">
  <span class="text-green-400">{{ post.num_likes }}</span>
</InfoTooltip>
```
**Applies to:** TopPostsFeed, TradeFeed, AgentProfileCards.

---

## Edit Footprint

- **2 new files:** `frontend/src/components/InfoTooltip.vue`, `frontend/src/data/tooltipCopy.js`
- **~20 existing components edited:** template-level wrapping, no logic changes
- **~5 canvas components:** tooltip function edits to append meaning line
