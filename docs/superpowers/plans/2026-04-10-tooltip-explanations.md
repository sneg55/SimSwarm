# Tooltip Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explanatory hover tooltips to every visible metric across the simulation results UI (Story, Data, Graph views).

**Architecture:** A reusable `<InfoTooltip>` Vue 3 component wraps metrics and reads copy from a central `tooltipCopy.js` dictionary. DOM metrics get the wrapper + `ⓘ` icon; SVG hover tooltips get an appended meaning line. No external dependencies.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS, Vitest

**Spec:** `docs/superpowers/specs/2026-04-10-tooltip-explanations-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `frontend/src/data/tooltipCopy.js` | Central dictionary of all tooltip copy + `normalizeKey` utility |
| Create | `frontend/src/components/InfoTooltip.vue` | Reusable tooltip wrapper component |
| Create | `frontend/src/components/__tests__/InfoTooltip.spec.js` | Unit tests for InfoTooltip |
| Create | `frontend/src/data/__tests__/tooltipCopy.spec.js` | Unit tests for tooltip dictionary + normalizeKey |
| Modify | `frontend/src/components/results/CoalitionCard.vue` | Wrap agents + strength metrics |
| Modify | `frontend/src/components/results/FindingCard.vue` | Wrap metric display |
| Modify | `frontend/src/components/results/ConfidenceGrid.vue` | Wrap animated values |
| Modify | `frontend/src/components/results/SentimentBars.vue` | Wrap bar values |
| Modify | `frontend/src/components/results/EngagementCompact.vue` | Wrap totalPosts + totalLikes |
| Modify | `frontend/src/components/results/MarketCurveCompact.vue` | Wrap currentYes percentage |
| Modify | `frontend/src/views/SimulationResults.vue:29-35` | Wrap tier + dates in header |
| Modify | `frontend/src/components/data/TopPostsFeed.vue` | Wrap likes/shares/dislikes |
| Modify | `frontend/src/components/data/TradeFeed.vue` | Wrap price + cost |
| Modify | `frontend/src/components/data/AgentProfileCards.vue` | Wrap MBTI badge |
| Modify | `frontend/src/components/data/SocialGraphView.vue:8-9` | Wrap legend text items |
| Modify | `frontend/src/components/data/MarketCurveChart.vue:36-42` | Enhance hover tooltip with meaning line |
| Modify | `frontend/src/components/data/EngagementChart.vue:18-26` | Enhance hover tooltip with meaning line |
| Modify | `frontend/src/components/data/AgentTrajectoryChart.vue:21-29` | Enhance hover tooltip with meaning line |
| Modify | `frontend/src/components/graph/GraphLegend.vue` | Wrap entity counts + sentiment counts |
| Modify | `frontend/src/components/graph/GraphDetailPanel.vue:59-79` | Wrap connectionCount, sentiment, stance, influence |
| Modify | `frontend/src/components/graph/GraphVisualization.vue:104-128` | Enhance hover tooltip with meaning line |

---

### Task 1: Create tooltip copy dictionary

**Files:**
- Create: `frontend/src/data/tooltipCopy.js`
- Create: `frontend/src/data/__tests__/tooltipCopy.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/data/__tests__/tooltipCopy.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { tooltipCopy, normalizeKey, getTooltip } from '../tooltipCopy.js'

describe('tooltipCopy', () => {
  it('exports a non-empty dictionary', () => {
    expect(Object.keys(tooltipCopy).length).toBeGreaterThan(30)
  })

  it('every entry has title, meaning, and calculation strings', () => {
    for (const [key, entry] of Object.entries(tooltipCopy)) {
      expect(entry.title, `${key} missing title`).toBeTruthy()
      expect(typeof entry.title).toBe('string')
      expect(entry.meaning, `${key} missing meaning`).toBeTruthy()
      expect(typeof entry.meaning).toBe('string')
      expect(entry.calculation, `${key} missing calculation`).toBeTruthy()
      expect(typeof entry.calculation).toBe('string')
    }
  })
})

describe('normalizeKey', () => {
  it('converts space-separated words to camelCase', () => {
    expect(normalizeKey('Agents Active')).toBe('agentsActive')
  })

  it('handles single word', () => {
    expect(normalizeKey('Consensus')).toBe('consensus')
  })

  it('handles already camelCase', () => {
    expect(normalizeKey('agentsActive')).toBe('agentsActive')
  })

  it('handles mixed case with multiple spaces', () => {
    expect(normalizeKey('Total Market Volume')).toBe('totalMarketVolume')
  })
})

describe('getTooltip', () => {
  it('returns entry for known key', () => {
    const entry = getTooltip('coalitionCard.strength')
    expect(entry).toBeTruthy()
    expect(entry.title).toBe('Coalition Strength')
  })

  it('returns null for unknown key', () => {
    expect(getTooltip('nonexistent.key')).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/data/__tests__/tooltipCopy.spec.js`
Expected: FAIL — module not found

- [ ] **Step 3: Create the tooltip dictionary**

Create `frontend/src/data/tooltipCopy.js`:

```js
/**
 * Central tooltip copy dictionary.
 * Key format: camelCaseComponentName.camelCaseMetricName
 * Each entry: { title, meaning, calculation }
 */
export const tooltipCopy = {
  // ── Story View: ConfidenceGrid ──
  'confidenceGrid.agentsActive': {
    title: 'Agents Active',
    meaning: 'The number of simulated agents that participated in this scenario. Each agent has its own personality, knowledge, and goals.',
    calculation: 'Counted from the total agents that posted, traded, or interacted at least once during the simulation.',
  },
  'confidenceGrid.roundsCompleted': {
    title: 'Rounds Completed',
    meaning: 'How many cycles the simulation ran. Each round represents a period where all agents can act — post, trade, react, and update their beliefs.',
    calculation: 'One round completes when every active agent has had a chance to act. The number depends on the tier and complexity of your scenario.',
  },
  'confidenceGrid.totalInteractions': {
    title: 'Total Interactions',
    meaning: 'The combined number of actions agents took — posts, likes, comments, trades, and follows. Higher numbers mean a more active simulated community.',
    calculation: 'Sum of every discrete action across all agents and all rounds.',
  },

  // ── Story View: SentimentBars ──
  'sentimentBars.overallSentiment': {
    title: 'Overall Sentiment',
    meaning: 'The general emotional tone across all agents by the end of the simulation. Positive means the community leaned favorable; negative means skeptical or opposed.',
    calculation: 'Averaged from each agent\'s final sentiment score, which updates every round based on what they read, post, and experience.',
  },
  'sentimentBars.consensus': {
    title: 'Consensus',
    meaning: 'How much agents agreed with each other by the end. High consensus means a dominant shared view emerged; low means opinions stayed divided.',
    calculation: 'Measured from the spread of final agent positions — tighter clustering means higher consensus.',
  },
  'sentimentBars.volatility': {
    title: 'Volatility',
    meaning: 'How much opinions shifted during the simulation. High volatility means agents frequently changed their minds; low means positions were stable early.',
    calculation: 'Tracked from round-to-round sentiment changes across all agents, then averaged.',
  },
  'sentimentBars.engagement': {
    title: 'Engagement',
    meaning: 'How actively agents participated relative to opportunities. High engagement means agents chose to post and interact rather than stay silent.',
    calculation: 'Ratio of actions agents actually took versus the maximum possible actions across all rounds.',
  },

  // ── Story View: CoalitionCard ──
  'coalitionCard.agents': {
    title: 'Coalition Members',
    meaning: 'How many agents belong to this group. Coalitions form naturally when agents with similar views start interacting and reinforcing each other.',
    calculation: 'Counted from agents the simulation identified as behaviorally clustered — they share stances, interact frequently, and reference similar ideas.',
  },
  'coalitionCard.strength': {
    title: 'Coalition Strength',
    meaning: 'How tightly aligned this group is. A high percentage means members consistently agree with each other and act in coordination.',
    calculation: 'Measured from how often coalition members take the same stance and interact with each other versus with outsiders, across all rounds.',
  },

  // ── Story View: FindingCard ──
  'findingCard.metric': {
    title: 'Finding Metric',
    meaning: 'A standout number that captures the scale or impact of this finding.',
    calculation: 'Derived from the specific pattern described — may reflect engagement multiples, sentiment shifts, or adoption rates depending on the finding.',
  },

  // ── Story View: EngagementCompact ──
  'engagementCompact.totalPosts': {
    title: 'Total Posts',
    meaning: 'The total number of original posts agents published across all rounds. Posts are how agents share their views and influence others.',
    calculation: 'Sum of all CREATE_POST actions by every agent across every round.',
  },
  'engagementCompact.totalLikes': {
    title: 'Total Likes',
    meaning: 'How many times agents endorsed each other\'s content. Likes signal agreement and amplify a post\'s reach within the simulation.',
    calculation: 'Sum of all LIKE_POST actions across every agent and round.',
  },

  // ── Story View: MarketCurveCompact ──
  'marketCurveCompact.currentYes': {
    title: 'Current YES Probability',
    meaning: 'The market\'s latest estimate that the predicted outcome will happen. Think of it like a crowd-sourced confidence level — agents bet real simulation credits on what they believe.',
    calculation: 'Derived from the last trade price. When agents buy YES shares, the price rises; when they sell, it falls. The percentage reflects the balance of conviction.',
  },

  // ── Story View: SimulationResults header ──
  'simulationResults.tier': {
    title: 'Simulation Tier',
    meaning: 'The complexity level of this run. Higher tiers use more agents, more rounds, and more capable AI models — producing richer and more nuanced results.',
    calculation: 'Set when the simulation was created. Each tier defines agent count, round count, context window, and GPU allocation.',
  },
  'simulationResults.startedAt': {
    title: 'Started',
    meaning: 'When the simulation began processing on the GPU.',
    calculation: 'Recorded when the job was picked up by a GPU worker.',
  },
  'simulationResults.completedAt': {
    title: 'Completed',
    meaning: 'When the simulation finished and results became available.',
    calculation: 'Recorded when the final round completes and all data is extracted and stored.',
  },

  // ── Data View: MarketCurveChart ──
  'marketCurveChart.currentPrice': {
    title: 'Current Price',
    meaning: 'The latest market probability for this outcome.',
    calculation: 'Last trade price in the market\'s order book.',
  },
  'marketCurveChart.tooltipYes': {
    title: 'YES Price',
    meaning: 'What the market thinks is the probability this outcome happens.',
    calculation: 'Set by the last trade — when an agent buys YES shares, the price moves up.',
  },
  'marketCurveChart.tooltipNo': {
    title: 'NO Price',
    meaning: 'The implied probability this outcome does not happen.',
    calculation: 'Calculated as 100% minus the YES price. Always moves inversely.',
  },
  'marketCurveChart.tooltipVolume': {
    title: 'Trade Volume',
    meaning: 'Total simulation currency spent on this trade. Larger trades signal stronger conviction from the agent.',
    calculation: 'The dollar cost the agent paid for the shares in this transaction.',
  },
  'marketCurveChart.hoverMeaning': {
    title: 'Trade',
    meaning: 'Each trade shifts the price based on how much an agent is willing to pay for their predicted outcome.',
    calculation: '',
  },

  // ── Data View: EngagementChart ──
  'engagementChart.posts': {
    title: 'Posts This Round',
    meaning: 'Original content published by agents during this round.',
    calculation: 'Count of CREATE_POST actions in this specific round.',
  },
  'engagementChart.likes': {
    title: 'Likes This Round',
    meaning: 'Endorsements agents gave to each other\'s content this round.',
    calculation: 'Count of LIKE_POST and LIKE_COMMENT actions in this round.',
  },
  'engagementChart.comments': {
    title: 'Comments This Round',
    meaning: 'Replies and reactions agents wrote on each other\'s posts.',
    calculation: 'Count of CREATE_COMMENT actions in this round.',
  },
  'engagementChart.activeAgents': {
    title: 'Active Agents',
    meaning: 'How many agents did something this round — posted, liked, commented, or traded. Idle agents stayed quiet.',
    calculation: 'Count of distinct agents with at least one action in this round.',
  },
  'engagementChart.hoverMeaning': {
    title: 'Round Activity',
    meaning: 'What happened during this simulation cycle — all agent posts, reactions, and social interactions for the round.',
    calculation: '',
  },

  // ── Data View: AgentTrajectoryChart ──
  'agentTrajectoryChart.sentiment': {
    title: 'Agent Sentiment',
    meaning: 'This agent\'s emotional position at this point in the simulation. +1 is fully supportive, -1 is fully opposed, 0 is neutral.',
    calculation: 'Updated each round based on what the agent posted, read, and how others responded to them. Reflects cumulative belief evolution.',
  },
  'agentTrajectoryChart.hoverMeaning': {
    title: 'Agent Position',
    meaning: 'How this agent\'s opinion evolved through the simulation based on their posts, interactions, and the content they consumed.',
    calculation: '',
  },

  // ── Data View: TopPostsFeed ──
  'topPostsFeed.likes': {
    title: 'Likes',
    meaning: 'How many other agents endorsed this post. Popular posts shape the conversation and pull sentiment toward them.',
    calculation: 'Count of LIKE_POST actions targeting this specific post.',
  },
  'topPostsFeed.shares': {
    title: 'Shares',
    meaning: 'How many agents amplified this post to their followers. Shares extend a post\'s reach beyond the original audience.',
    calculation: 'Count of REPOST and QUOTE_POST actions targeting this post.',
  },
  'topPostsFeed.dislikes': {
    title: 'Dislikes',
    meaning: 'How many agents actively disagreed with this post. Dislikes signal opposition and can dampen a post\'s influence.',
    calculation: 'Count of DISLIKE_POST actions targeting this post.',
  },

  // ── Data View: TradeFeed ──
  'tradeFeed.price': {
    title: 'Trade Price',
    meaning: 'The probability level at which this agent bought or sold. A BUY at 70% means the agent believes there\'s at least a 70% chance the outcome happens.',
    calculation: 'The market price at the moment this trade executed.',
  },
  'tradeFeed.cost': {
    title: 'Trade Cost',
    meaning: 'How much simulation currency the agent spent on this position. Larger bets mean the agent had stronger conviction.',
    calculation: 'Calculated from share quantity multiplied by price. Reflects the agent\'s resource commitment.',
  },

  // ── Data View: AgentProfileCards ──
  'agentProfileCards.mbti': {
    title: 'Personality Type',
    meaning: 'The agent\'s simulated personality using the MBTI framework. This shapes how the agent processes information, makes decisions, and interacts with others.',
    calculation: 'Assigned during agent creation based on the persona configuration. Influences posting style, risk tolerance, and social behavior.',
  },

  // ── Data View: SocialGraphView ──
  'socialGraphView.nodeSize': {
    title: 'Node Size',
    meaning: 'Larger nodes represent agents with more followers. These agents have more social influence in the simulation.',
    calculation: 'Scaled from each agent\'s follower count using a square root scale for readability.',
  },
  'socialGraphView.mutualEdge': {
    title: 'Bright Edges',
    meaning: 'A bright connection means both agents follow each other — a mutual relationship. These tend to be the strongest influence channels.',
    calculation: 'Detected when agent A follows agent B and agent B follows agent A.',
  },

  // ── Graph View: GraphLegend ──
  'graphLegend.entityCount': {
    title: 'Entity Count',
    meaning: 'How many knowledge graph nodes belong to this type. The graph captures people, organizations, concepts, and events the simulation discovered.',
    calculation: 'Counted from all nodes extracted from agent conversations and enrichment data, filtered by this entity type.',
  },
  'graphLegend.sentimentPositive': {
    title: 'Positive Sentiment',
    meaning: 'Nodes the simulation community viewed favorably — they were discussed in supportive or optimistic terms.',
    calculation: 'Nodes with a final averaged sentiment score above +0.2.',
  },
  'graphLegend.sentimentNegative': {
    title: 'Negative Sentiment',
    meaning: 'Nodes the community viewed unfavorably — discussed with skepticism, criticism, or opposition.',
    calculation: 'Nodes with a final averaged sentiment score below -0.2.',
  },
  'graphLegend.sentimentNeutral': {
    title: 'Neutral Sentiment',
    meaning: 'Nodes discussed without strong positive or negative feeling — factual references or divided opinions that balanced out.',
    calculation: 'Nodes with a final averaged sentiment score between -0.2 and +0.2.',
  },

  // ── Graph View: GraphDetailPanel ──
  'graphDetailPanel.connectionCount': {
    title: 'Connections',
    meaning: 'How many other entities in the knowledge graph are linked to this one. More connections means this entity was referenced in more contexts.',
    calculation: 'Count of all incoming and outgoing relationships for this node.',
  },
  'graphDetailPanel.sentiment': {
    title: 'Sentiment',
    meaning: 'The community\'s overall feeling toward this entity. Positive values mean favorable discussion; negative means critical or opposed.',
    calculation: 'Averaged from sentiment scores across all agent mentions and interactions involving this entity.',
  },
  'graphDetailPanel.stance': {
    title: 'Stance',
    meaning: 'The dominant community position on this entity — supportive, opposing, or observer.',
    calculation: 'Derived from the balance of positive vs negative interactions. Supportive if sentiment > +0.2, opposing if < -0.2, observer otherwise.',
  },
  'graphDetailPanel.influenceWeight': {
    title: 'Influence Weight',
    meaning: 'How much this entity affected the simulation\'s narrative. Higher multipliers mean this entity was central to how opinions formed and spread.',
    calculation: 'Calculated from connection count, mention frequency, and the sentiment intensity of interactions involving this entity.',
  },
  'graphDetailPanel.roundNumber': {
    title: 'Round',
    meaning: 'Which simulation cycle this activity happened in. Earlier rounds show initial reactions; later rounds show evolved positions.',
    calculation: 'The sequential round number when this specific action was recorded.',
  },

  // ── Graph View: GraphVisualization hover tooltip ──
  'graphVisualization.hoverSentiment': {
    title: 'Sentiment',
    meaning: 'How the simulated community feels about this entity.',
    calculation: 'Averaged from all agent mentions — positive means supportive discussion, negative means critical.',
  },
  'graphVisualization.hoverStance': {
    title: 'Stance',
    meaning: 'The community\'s dominant position toward this entity.',
    calculation: 'Classified from the sentiment score — supportive, opposing, or neutral observer.',
  },
  'graphVisualization.hoverMeaning': {
    title: 'Entity',
    meaning: 'A person, organization, concept, or event discovered during the simulation through agent conversations and web enrichment.',
    calculation: '',
  },
}

/**
 * Convert a display label to a camelCase dictionary key.
 * "Agents Active" → "agentsActive"
 * "Total Market Volume" → "totalMarketVolume"
 */
export function normalizeKey(label) {
  const words = label.trim().split(/\s+/)
  return words
    .map((w, i) => i === 0 ? w[0].toLowerCase() + w.slice(1) : w[0].toUpperCase() + w.slice(1))
    .join('')
}

/**
 * Look up a tooltip entry by key. Returns null if not found.
 */
export function getTooltip(key) {
  return tooltipCopy[key] || null
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/data/__tests__/tooltipCopy.spec.js`
Expected: PASS — all assertions pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/data/tooltipCopy.js frontend/src/data/__tests__/tooltipCopy.spec.js
git commit -m "feat: add tooltip copy dictionary with normalizeKey utility"
```

---

### Task 2: Create InfoTooltip component

**Files:**
- Create: `frontend/src/components/InfoTooltip.vue`
- Create: `frontend/src/components/__tests__/InfoTooltip.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/__tests__/InfoTooltip.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import InfoTooltip from '../InfoTooltip.vue'

describe('InfoTooltip', () => {
  it('renders slot content', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span class="metric">82%</span>' },
    })
    expect(wrapper.find('.metric').text()).toBe('82%')
  })

  it('renders info icon for known copyKey', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
    })
    expect(wrapper.find('[data-testid="info-icon"]').exists()).toBe(true)
  })

  it('does not render icon for unknown copyKey', () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'nonexistent.metric' },
      slots: { default: '<span>42</span>' },
    })
    expect(wrapper.find('[data-testid="info-icon"]').exists()).toBe(false)
  })

  it('shows tooltip on mouseenter', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseenter')
    // Wait for 200ms hover delay
    await new Promise(r => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('Coalition Strength')
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('How tightly aligned')
    expect(wrapper.find('[data-testid="tooltip-panel"]').text()).toContain('Calculated from:')
    wrapper.unmount()
  })

  it('hides tooltip on mouseleave', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseenter')
    await new Promise(r => setTimeout(r, 250))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(true)
    await wrapper.find('[data-testid="tooltip-trigger"]').trigger('mouseleave')
    await new Promise(r => setTimeout(r, 200))
    expect(wrapper.find('[data-testid="tooltip-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('has correct aria attributes', async () => {
    const wrapper = mount(InfoTooltip, {
      props: { copyKey: 'coalitionCard.strength' },
      slots: { default: '<span>82%</span>' },
      attachTo: document.body,
    })
    const icon = wrapper.find('[data-testid="info-icon"]')
    expect(icon.attributes('role')).toBe('button')
    expect(icon.attributes('tabindex')).toBe('0')
    expect(icon.attributes('aria-label')).toBe('More info')
    wrapper.unmount()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/InfoTooltip.spec.js`
Expected: FAIL — component not found

- [ ] **Step 3: Create the InfoTooltip component**

Create `frontend/src/components/InfoTooltip.vue`:

```vue
<template>
  <span
    class="inline-flex items-center gap-0.5 relative"
    data-testid="tooltip-trigger"
    @mouseenter="onEnter"
    @mouseleave="onLeave"
    @focusin="onEnter"
    @focusout="onLeave"
    @keydown.escape="hide"
  >
    <slot />
    <span
      v-if="entry"
      data-testid="info-icon"
      role="button"
      tabindex="0"
      aria-label="More info"
      :aria-describedby="tooltipId"
      class="inline-flex items-center justify-center rounded-full cursor-help transition-colors"
      :class="iconSize === 'md' ? 'w-4 h-4 text-[10px]' : 'w-3 h-3 text-[8px]'"
      style="color: rgba(34,211,238,0.4);"
      @mouseenter="onEnter"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <svg viewBox="0 0 16 16" fill="currentColor" class="w-full h-full">
        <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2.5a1 1 0 110 2 1 1 0 010-2zM6.5 7h2v4.5h-2V7h1z" fill-rule="evenodd"/>
      </svg>
    </span>
    <Teleport to="body">
      <div
        v-if="visible && entry"
        :id="tooltipId"
        ref="panelRef"
        role="tooltip"
        data-testid="tooltip-panel"
        class="fixed z-[9999] max-w-[280px] rounded-lg px-3.5 py-3 border pointer-events-auto"
        style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3);"
        :style="panelStyle"
        :class="animClass"
        @mouseenter="onEnter"
        @mouseleave="onLeave"
      >
        <!-- Arrow -->
        <div
          class="absolute w-2.5 h-2.5 rotate-45"
          style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2);"
          :style="arrowStyle"
        />
        <div class="text-teal-300 text-[10px] font-semibold uppercase tracking-wider mb-1.5">{{ entry.title }}</div>
        <p class="text-gray-200 text-sm leading-relaxed mb-0">{{ entry.meaning }}</p>
        <template v-if="entry.calculation">
          <div class="border-t my-2" style="border-color: rgba(34,211,238,0.1);" />
          <p class="text-gray-400 text-xs leading-relaxed">
            <span style="color: rgba(34,211,238,0.6);">Calculated from: </span>{{ entry.calculation }}
          </p>
        </template>
      </div>
    </Teleport>
  </span>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import { getTooltip } from '../data/tooltipCopy.js'

const props = defineProps({
  copyKey: { type: String, required: true },
  position: { type: String, default: 'top' },
  iconSize: { type: String, default: 'sm' },
})

const entry = computed(() => getTooltip(props.copyKey))
const tooltipId = computed(() => `tt-${props.copyKey.replace(/\./g, '-')}`)

const visible = ref(false)
const animClass = ref('')
const panelRef = ref(null)
const panelStyle = ref({})
const arrowStyle = ref({})

let showTimer = null
let hideTimer = null

function onEnter() {
  if (!entry.value) return
  clearTimeout(hideTimer)
  if (visible.value) return
  showTimer = setTimeout(() => {
    visible.value = true
    nextTick(position)
    requestAnimationFrame(() => { animClass.value = 'tooltip-visible' })
  }, 200)
}

function onLeave() {
  clearTimeout(showTimer)
  hideTimer = setTimeout(hide, 150)
}

function hide() {
  visible.value = false
  animClass.value = ''
}

function toggle() {
  if (visible.value) hide()
  else onEnter()
}

function position() {
  if (!panelRef.value) return
  const trigger = panelRef.value?.parentElement?.querySelector('[data-testid="tooltip-trigger"]')
    || document.querySelector(`[aria-describedby="${tooltipId.value}"]`)?.closest('[data-testid="tooltip-trigger"]')
  if (!trigger) return

  const triggerRect = trigger.getBoundingClientRect()
  const panel = panelRef.value
  const panelRect = panel.getBoundingClientRect()
  const gap = 8

  let placement = props.position
  const fits = {
    top: triggerRect.top - panelRect.height - gap > 0,
    bottom: triggerRect.bottom + panelRect.height + gap < window.innerHeight,
    left: triggerRect.left - panelRect.width - gap > 0,
    right: triggerRect.right + panelRect.width + gap < window.innerWidth,
  }
  if (!fits[placement]) {
    const opposite = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' }
    placement = fits[opposite[placement]] ? opposite[placement] : 'top'
  }

  let top, left
  if (placement === 'top') {
    top = triggerRect.top - panelRect.height - gap
    left = triggerRect.left + triggerRect.width / 2 - panelRect.width / 2
    arrowStyle.value = { bottom: '-5px', left: '50%', transform: 'translateX(-50%) rotate(45deg)', borderRight: '1px solid rgba(34,211,238,0.2)', borderBottom: '1px solid rgba(34,211,238,0.2)' }
  } else if (placement === 'bottom') {
    top = triggerRect.bottom + gap
    left = triggerRect.left + triggerRect.width / 2 - panelRect.width / 2
    arrowStyle.value = { top: '-5px', left: '50%', transform: 'translateX(-50%) rotate(45deg)', borderLeft: '1px solid rgba(34,211,238,0.2)', borderTop: '1px solid rgba(34,211,238,0.2)' }
  } else if (placement === 'left') {
    top = triggerRect.top + triggerRect.height / 2 - panelRect.height / 2
    left = triggerRect.left - panelRect.width - gap
    arrowStyle.value = { right: '-5px', top: '50%', transform: 'translateY(-50%) rotate(45deg)', borderTop: '1px solid rgba(34,211,238,0.2)', borderRight: '1px solid rgba(34,211,238,0.2)' }
  } else {
    top = triggerRect.top + triggerRect.height / 2 - panelRect.height / 2
    left = triggerRect.right + gap
    arrowStyle.value = { left: '-5px', top: '50%', transform: 'translateY(-50%) rotate(45deg)', borderBottom: '1px solid rgba(34,211,238,0.2)', borderLeft: '1px solid rgba(34,211,238,0.2)' }
  }

  // Clamp to viewport
  left = Math.max(8, Math.min(left, window.innerWidth - panelRect.width - 8))
  top = Math.max(8, Math.min(top, window.innerHeight - panelRect.height - 8))

  panelStyle.value = { top: `${top}px`, left: `${left}px` }
}

// Close on outside click (mobile)
function onDocClick(e) {
  if (visible.value && panelRef.value && !panelRef.value.contains(e.target)) {
    const trigger = e.target.closest('[data-testid="tooltip-trigger"]')
    if (!trigger || !trigger.contains(document.querySelector(`[aria-describedby="${tooltipId.value}"]`))) {
      hide()
    }
  }
}

watch(visible, (v) => {
  if (v) document.addEventListener('click', onDocClick, true)
  else document.removeEventListener('click', onDocClick, true)
})

onBeforeUnmount(() => {
  clearTimeout(showTimer)
  clearTimeout(hideTimer)
  document.removeEventListener('click', onDocClick, true)
})
</script>

<style scoped>
.tooltip-visible {
  opacity: 1 !important;
  transform: translateY(0) !important;
}
[data-testid="tooltip-panel"] {
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 150ms ease-out, transform 150ms ease-out;
}
@media (prefers-reduced-motion: reduce) {
  [data-testid="tooltip-panel"] {
    transition: none;
  }
}
[data-testid="info-icon"]:hover,
[data-testid="info-icon"]:focus-visible {
  color: rgba(34, 211, 238, 0.8) !important;
}
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/InfoTooltip.spec.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/InfoTooltip.vue frontend/src/components/__tests__/InfoTooltip.spec.js
git commit -m "feat: add InfoTooltip component with dark glass styling"
```

---

### Task 3: Integrate tooltips into Story View components

**Files:**
- Modify: `frontend/src/components/results/CoalitionCard.vue`
- Modify: `frontend/src/components/results/FindingCard.vue`
- Modify: `frontend/src/components/results/ConfidenceGrid.vue`
- Modify: `frontend/src/components/results/SentimentBars.vue`
- Modify: `frontend/src/components/results/EngagementCompact.vue`
- Modify: `frontend/src/components/results/MarketCurveCompact.vue`
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Update CoalitionCard.vue**

Add import and wrap line 8:

```vue
<!-- Replace line 8 -->
<!-- Before: -->
<div class="font-mono text-[11px] text-mist-slate mt-2">{{ agents }} agents &middot; Strength: {{ strength }}%</div>

<!-- After: -->
<div class="font-mono text-[11px] text-mist-slate mt-2">
  <InfoTooltip copyKey="coalitionCard.agents">{{ agents }} agents</InfoTooltip>
  &middot;
  <InfoTooltip copyKey="coalitionCard.strength">Strength: {{ strength }}%</InfoTooltip>
</div>
```

Add to script:
```vue
<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({
  name: { type: String, required: true },
  description: { type: String, required: true },
  agents: { type: Number, required: true },
  strength: { type: Number, required: true },
  color: { type: String, default: '#22D3EE' },
})
</script>
```

- [ ] **Step 2: Update FindingCard.vue**

Wrap the metric display at lines 7-11:

```vue
<!-- Before: -->
<div v-if="metric" class="inline-flex items-center gap-1.5 mt-3 font-mono text-sm px-2.5 py-1 rounded-md"
  :style="{ color: accentColor, background: accentColor + '14' }">
  <span class="w-1.5 h-1.5 rounded-full" :style="{ background: accentColor }" />
  {{ metric }}
</div>

<!-- After: -->
<InfoTooltip v-if="metric" copyKey="findingCard.metric">
  <div class="inline-flex items-center gap-1.5 mt-3 font-mono text-sm px-2.5 py-1 rounded-md"
    :style="{ color: accentColor, background: accentColor + '14' }">
    <span class="w-1.5 h-1.5 rounded-full" :style="{ background: accentColor }" />
    {{ metric }}
  </div>
</InfoTooltip>
```

Add to script:
```vue
<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ /* existing props unchanged */ })
</script>
```

- [ ] **Step 3: Update ConfidenceGrid.vue**

Wrap each item's value and label (lines 8-11) with dynamic key:

```vue
<!-- Before: -->
<div class="font-mono text-3xl font-bold tracking-tight mb-1 transition-all duration-700" :style="{ color: item.color }">
  {{ visible ? item.value : '0' }}
</div>
<div class="text-xs text-mist-slate uppercase tracking-wider">{{ item.label }}</div>

<!-- After: -->
<InfoTooltip :copyKey="`confidenceGrid.${normalizeKey(item.label)}`" position="bottom">
  <div>
    <div class="font-mono text-3xl font-bold tracking-tight mb-1 transition-all duration-700" :style="{ color: item.color }">
      {{ visible ? item.value : '0' }}
    </div>
    <div class="text-xs text-mist-slate uppercase tracking-wider">{{ item.label }}</div>
  </div>
</InfoTooltip>
```

Add to script:
```vue
import { ref, onMounted, onUnmounted } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
import { normalizeKey } from '../../data/tooltipCopy.js'
```

- [ ] **Step 4: Update SentimentBars.vue**

Wrap each bar's value at line 10 with dynamic key:

```vue
<!-- Before: -->
<span class="font-mono text-sm min-w-[48px] text-right" :style="{ color: bar.valueColor }">{{ bar.value }}</span>

<!-- After: -->
<InfoTooltip :copyKey="`sentimentBars.${normalizeKey(bar.label)}`">
  <span class="font-mono text-sm min-w-[48px] text-right" :style="{ color: bar.valueColor }">{{ bar.value }}</span>
</InfoTooltip>
```

Add to script:
```vue
import { ref, onMounted, onUnmounted } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
import { normalizeKey } from '../../data/tooltipCopy.js'
```

- [ ] **Step 5: Update EngagementCompact.vue**

Wrap the stats line at lines 5-7:

```vue
<!-- Before: -->
<div class="text-xs text-mist-slate">
  {{ totalPosts }} posts<template v-if="totalLikes > 0"> · {{ totalLikes }} likes</template>
</div>

<!-- After: -->
<div class="text-xs text-mist-slate">
  <InfoTooltip copyKey="engagementCompact.totalPosts">{{ totalPosts }} posts</InfoTooltip>
  <template v-if="totalLikes > 0"> · <InfoTooltip copyKey="engagementCompact.totalLikes">{{ totalLikes }} likes</InfoTooltip></template>
</div>
```

Add to script:
```vue
import { computed } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
```

- [ ] **Step 6: Update MarketCurveCompact.vue**

Wrap the YES percentage at lines 5-7:

```vue
<!-- Before: -->
<div class="text-xs font-mono">
  <span class="text-green-400">{{ currentYes }}%</span> YES
</div>

<!-- After: -->
<div class="text-xs font-mono">
  <InfoTooltip copyKey="marketCurveCompact.currentYes"><span class="text-green-400">{{ currentYes }}%</span> YES</InfoTooltip>
</div>
```

Add to script:
```vue
import { computed } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
```

- [ ] **Step 7: Update SimulationResults.vue header**

Wrap the tier and dates at lines 31-35:

```vue
<!-- Before: -->
<p class="text-sm text-mist-slate capitalize">
  {{ job.tier }} tier
  <span v-if="job.created_at"> &bull; Started {{ formatDate(job.created_at) }}</span>
  <span v-if="job.completed_at"> &bull; Completed {{ formatDate(job.completed_at) }}</span>
</p>

<!-- After: -->
<p class="text-sm text-mist-slate capitalize">
  <InfoTooltip copyKey="simulationResults.tier">{{ job.tier }} tier</InfoTooltip>
  <span v-if="job.created_at"> &bull; <InfoTooltip copyKey="simulationResults.startedAt">Started {{ formatDate(job.created_at) }}</InfoTooltip></span>
  <span v-if="job.completed_at"> &bull; <InfoTooltip copyKey="simulationResults.completedAt">Completed {{ formatDate(job.completed_at) }}</InfoTooltip></span>
</p>
```

Add `import InfoTooltip from '../components/InfoTooltip.vue'` to the script imports.

- [ ] **Step 8: Run tests and verify nothing broke**

Run: `cd frontend && npx vitest run`
Expected: all existing tests pass

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/results/ frontend/src/views/SimulationResults.vue
git commit -m "feat: add tooltip explanations to Story View components"
```

---

### Task 4: Integrate tooltips into Data View components

**Files:**
- Modify: `frontend/src/components/data/TopPostsFeed.vue`
- Modify: `frontend/src/components/data/TradeFeed.vue`
- Modify: `frontend/src/components/data/AgentProfileCards.vue`
- Modify: `frontend/src/components/data/SocialGraphView.vue`

- [ ] **Step 1: Update TopPostsFeed.vue**

Wrap engagement metrics at lines 15-17:

```vue
<!-- Before: -->
<div class="flex gap-3 mt-1.5 text-[10px] text-mist-slate">
  <span v-if="post.num_likes" class="text-green-400">♥ {{ post.num_likes }}</span>
  <span v-if="post.num_shares">↻ {{ post.num_shares }}</span>
  <span v-if="post.num_dislikes" class="text-red-400">↓ {{ post.num_dislikes }}</span>
</div>

<!-- After: -->
<div class="flex gap-3 mt-1.5 text-[10px] text-mist-slate">
  <InfoTooltip v-if="post.num_likes" copyKey="topPostsFeed.likes"><span class="text-green-400">♥ {{ post.num_likes }}</span></InfoTooltip>
  <InfoTooltip v-if="post.num_shares" copyKey="topPostsFeed.shares"><span>↻ {{ post.num_shares }}</span></InfoTooltip>
  <InfoTooltip v-if="post.num_dislikes" copyKey="topPostsFeed.dislikes"><span class="text-red-400">↓ {{ post.num_dislikes }}</span></InfoTooltip>
</div>
```

Add to script:
```vue
<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ posts: { type: Array, default: () => [] } })
</script>
```

- [ ] **Step 2: Update TradeFeed.vue**

Wrap price and cost at lines 12-13:

```vue
<!-- Before: -->
<span class="text-mist-slate font-mono">@ {{ (trade.price * 100).toFixed(0) }}%</span>
<span class="text-mist-slate font-mono">${{ Math.round(trade.cost) }}</span>

<!-- After: -->
<InfoTooltip copyKey="tradeFeed.price"><span class="text-mist-slate font-mono">@ {{ (trade.price * 100).toFixed(0) }}%</span></InfoTooltip>
<InfoTooltip copyKey="tradeFeed.cost"><span class="text-mist-slate font-mono">${{ Math.round(trade.cost) }}</span></InfoTooltip>
```

Add to script:
```vue
<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ trades: { type: Array, default: () => [] } })
</script>
```

- [ ] **Step 3: Update AgentProfileCards.vue**

Wrap MBTI badge at line 12:

```vue
<!-- Before: -->
<span v-if="profile.mbti" class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.mbti }}</span>

<!-- After: -->
<InfoTooltip v-if="profile.mbti" copyKey="agentProfileCards.mbti"><span class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.mbti }}</span></InfoTooltip>
```

Add to script:
```vue
<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({ profiles: { type: Array, default: () => [] } })
</script>
```

- [ ] **Step 4: Update SocialGraphView.vue legend**

Wrap the legend text at lines 8-10:

```vue
<!-- Before: -->
<div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
  <span>Nodes = agents · Edges = follows · <span class="text-ocean-cyan">Bright edges</span> = mutual follows</span>
</div>

<!-- After: -->
<div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
  <span>
    <InfoTooltip copyKey="socialGraphView.nodeSize">Nodes = agents</InfoTooltip>
    · Edges = follows ·
    <InfoTooltip copyKey="socialGraphView.mutualEdge"><span class="text-ocean-cyan">Bright edges</span> = mutual follows</InfoTooltip>
  </span>
</div>
```

Add to script:
```vue
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'
import InfoTooltip from '../InfoTooltip.vue'
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/data/
git commit -m "feat: add tooltip explanations to Data View components"
```

---

### Task 5: Enhance SVG hover tooltips with meaning lines

**Files:**
- Modify: `frontend/src/components/data/MarketCurveChart.vue:36-42`
- Modify: `frontend/src/components/data/EngagementChart.vue:18-26`
- Modify: `frontend/src/components/data/AgentTrajectoryChart.vue:21-29`

- [ ] **Step 1: Update MarketCurveChart.vue hover tooltip**

Add import at top of script:
```js
import { getTooltip } from '../../data/tooltipCopy.js'
```

Replace the tooltip div at lines 36-42:

```vue
<!-- Before: -->
<div v-if="hovered && hovered.marketId === market.market_id"
  class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs"
  :style="{ left: hovered.x + 'px', top: (hovered.y - 60) + 'px', transform: 'translateX(-50%)' }">
  <div class="text-mist-slate">Trade #{{ hovered.idx }}</div>
  <div><span class="text-green-400">YES: {{ hovered.yes }}%</span> · <span class="text-red-400">NO: {{ hovered.no }}%</span></div>
  <div class="text-mist-slate">Vol: ${{ hovered.vol }}</div>
</div>

<!-- After: -->
<div v-if="hovered && hovered.marketId === market.market_id"
  class="absolute pointer-events-none rounded-lg px-3 py-2 text-xs border"
  style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3);"
  :style="{ left: hovered.x + 'px', top: (hovered.y - 80) + 'px', transform: 'translateX(-50%)', maxWidth: '240px' }">
  <div class="text-mist-slate">Trade #{{ hovered.idx }}</div>
  <div><span class="text-green-400">YES: {{ hovered.yes }}%</span> · <span class="text-red-400">NO: {{ hovered.no }}%</span></div>
  <div class="text-mist-slate">Vol: ${{ hovered.vol }}</div>
  <div class="border-t my-1.5" style="border-color: rgba(34,211,238,0.1);" />
  <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('marketCurveChart.hoverMeaning')?.meaning }}</div>
</div>
```

- [ ] **Step 2: Update EngagementChart.vue hover tooltip**

Add import at top of script:
```js
import { ref, computed } from 'vue'
import { getTooltip } from '../../data/tooltipCopy.js'
```

Replace the tooltip div at lines 18-26:

```vue
<!-- Before: -->
<div v-if="hovered"
  class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs z-10"
  :style="{ left: hovered.x + 'px', top: '8px' }">
  <div class="text-mist-slate">Round {{ hovered.round }}</div>
  <div><span style="color:#22D3EE;">Posts: {{ hovered.posts }}</span></div>
  <div><span style="color:#6EE7B7;">Likes: {{ hovered.likes }}</span></div>
  <div><span style="color:#A78BFA;">Comments: {{ hovered.comments }}</span></div>
  <div class="text-mist-slate">{{ hovered.agents }} active agents</div>
</div>

<!-- After: -->
<div v-if="hovered"
  class="absolute pointer-events-none rounded-lg px-3 py-2 text-xs z-10 border"
  style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3);"
  :style="{ left: hovered.x + 'px', top: '8px', maxWidth: '240px' }">
  <div class="text-mist-slate">Round {{ hovered.round }}</div>
  <div><span style="color:#22D3EE;">Posts: {{ hovered.posts }}</span></div>
  <div><span style="color:#6EE7B7;">Likes: {{ hovered.likes }}</span></div>
  <div><span style="color:#A78BFA;">Comments: {{ hovered.comments }}</span></div>
  <div class="text-mist-slate">{{ hovered.agents }} active agents</div>
  <div class="border-t my-1.5" style="border-color: rgba(34,211,238,0.1);" />
  <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('engagementChart.hoverMeaning')?.meaning }}</div>
</div>
```

- [ ] **Step 3: Update AgentTrajectoryChart.vue hover tooltip**

Add import at top of script:
```js
import { ref, computed } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'
import { getTooltip } from '../../data/tooltipCopy.js'
```

Replace the tooltip div at lines 21-29:

```vue
<!-- Before: -->
<div v-if="hovered"
  class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs z-10"
  :style="{ left: hovered.x + 'px', top: '8px' }">
  <div class="text-mist-foam font-medium">{{ hovered.name }}</div>
  <div class="text-mist-slate">Round {{ hovered.round }} · {{ hovered.posts }} posts</div>
  <div :style="{ color: hovered.sentiment >= 0 ? '#4ADE80' : '#F87171' }">
    Sentiment: {{ hovered.sentiment > 0 ? '+' : '' }}{{ hovered.sentiment }}
  </div>
</div>

<!-- After: -->
<div v-if="hovered"
  class="absolute pointer-events-none rounded-lg px-3 py-2 text-xs z-10 border"
  style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3);"
  :style="{ left: hovered.x + 'px', top: '8px', maxWidth: '240px' }">
  <div class="text-mist-foam font-medium">{{ hovered.name }}</div>
  <div class="text-mist-slate">Round {{ hovered.round }} · {{ hovered.posts }} posts</div>
  <div :style="{ color: hovered.sentiment >= 0 ? '#4ADE80' : '#F87171' }">
    Sentiment: {{ hovered.sentiment > 0 ? '+' : '' }}{{ hovered.sentiment }}
  </div>
  <div class="border-t my-1.5" style="border-color: rgba(34,211,238,0.1);" />
  <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('agentTrajectoryChart.hoverMeaning')?.meaning }}</div>
</div>
```

- [ ] **Step 4: Also wrap the static currentPrice in MarketCurveChart.vue**

At line 6, add InfoTooltip import and wrap:

```vue
<!-- Before: -->
{{ market.outcome_a }}: <span class="text-green-400 font-mono">{{ currentPrice(market) }}%</span>

<!-- After: -->
{{ market.outcome_a }}: <InfoTooltip copyKey="marketCurveChart.currentPrice"><span class="text-green-400 font-mono">{{ currentPrice(market) }}%</span></InfoTooltip>
```

Add import:
```js
import { ref } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
import { getTooltip } from '../../data/tooltipCopy.js'
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/data/MarketCurveChart.vue frontend/src/components/data/EngagementChart.vue frontend/src/components/data/AgentTrajectoryChart.vue
git commit -m "feat: add tooltip meaning lines to SVG hover tooltips"
```

---

### Task 6: Integrate tooltips into Graph View components

**Files:**
- Modify: `frontend/src/components/graph/GraphLegend.vue`
- Modify: `frontend/src/components/graph/GraphDetailPanel.vue`
- Modify: `frontend/src/components/graph/GraphVisualization.vue`

- [ ] **Step 1: Update GraphLegend.vue**

Wrap entity type count at line 22:

```vue
<!-- Before: -->
<span class="text-mist-slate font-mono text-[10px]">{{ et.count }}</span>

<!-- After: -->
<InfoTooltip copyKey="graphLegend.entityCount"><span class="text-mist-slate font-mono text-[10px]">{{ et.count }}</span></InfoTooltip>
```

Wrap sentiment counts at lines 37, 46, 55:

```vue
<!-- Line 37 before: -->
<span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.positive }}</span>
<!-- After: -->
<InfoTooltip copyKey="graphLegend.sentimentPositive"><span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.positive }}</span></InfoTooltip>

<!-- Line 46 before: -->
<span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.negative }}</span>
<!-- After: -->
<InfoTooltip copyKey="graphLegend.sentimentNegative"><span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.negative }}</span></InfoTooltip>

<!-- Line 55 before: -->
<span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.neutral }}</span>
<!-- After: -->
<InfoTooltip copyKey="graphLegend.sentimentNeutral"><span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.neutral }}</span></InfoTooltip>
```

Add import:
```js
import { computed } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
```

- [ ] **Step 2: Update GraphDetailPanel.vue properties section**

Wrap the four property values at lines 61-78:

```vue
<!-- Before (connectionCount, line 61-63): -->
<div v-if="node.connectionCount" class="text-center">
  <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.connectionCount }}</div>
  <div class="text-[10px] text-mist-slate uppercase">Connections</div>
</div>

<!-- After: -->
<div v-if="node.connectionCount" class="text-center">
  <InfoTooltip copyKey="graphDetailPanel.connectionCount" position="left">
    <div>
      <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.connectionCount }}</div>
      <div class="text-[10px] text-mist-slate uppercase">Connections</div>
    </div>
  </InfoTooltip>
</div>

<!-- Before (sentiment, line 65-69): -->
<div v-if="node.sentiment !== undefined && node.sentiment !== 0" class="text-center">
  <div class="font-mono text-lg font-bold"
    :style="{ color: node.sentiment > 0.2 ? '#6EE7B7' : node.sentiment < -0.2 ? '#FF6B6B' : '#94A3B8' }"
  >{{ node.sentiment > 0 ? '+' : '' }}{{ node.sentiment.toFixed(1) }}</div>
  <div class="text-[10px] text-mist-slate uppercase">Sentiment</div>
</div>

<!-- After: -->
<div v-if="node.sentiment !== undefined && node.sentiment !== 0" class="text-center">
  <InfoTooltip copyKey="graphDetailPanel.sentiment" position="left">
    <div>
      <div class="font-mono text-lg font-bold"
        :style="{ color: node.sentiment > 0.2 ? '#6EE7B7' : node.sentiment < -0.2 ? '#FF6B6B' : '#94A3B8' }"
      >{{ node.sentiment > 0 ? '+' : '' }}{{ node.sentiment.toFixed(1) }}</div>
      <div class="text-[10px] text-mist-slate uppercase">Sentiment</div>
    </div>
  </InfoTooltip>
</div>

<!-- Before (stance, line 71-73): -->
<div v-if="node.stance && node.stance !== 'neutral'" class="text-center">
  <div class="font-mono text-lg font-bold" :style="{ color: stanceColor }">{{ node.stance }}</div>
  <div class="text-[10px] text-mist-slate uppercase">Stance</div>
</div>

<!-- After: -->
<div v-if="node.stance && node.stance !== 'neutral'" class="text-center">
  <InfoTooltip copyKey="graphDetailPanel.stance" position="left">
    <div>
      <div class="font-mono text-lg font-bold" :style="{ color: stanceColor }">{{ node.stance }}</div>
      <div class="text-[10px] text-mist-slate uppercase">Stance</div>
    </div>
  </InfoTooltip>
</div>

<!-- Before (influence, line 75-77): -->
<div v-if="node.influenceWeight != null && node.influenceWeight !== 1.0" class="text-center">
  <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.influenceWeight.toFixed(1) }}x</div>
  <div class="text-[10px] text-mist-slate uppercase">Influence</div>
</div>

<!-- After: -->
<div v-if="node.influenceWeight != null && node.influenceWeight !== 1.0" class="text-center">
  <InfoTooltip copyKey="graphDetailPanel.influenceWeight" position="left">
    <div>
      <div class="font-mono text-lg font-bold" :style="{ color: nodeColor }">{{ node.influenceWeight.toFixed(1) }}x</div>
      <div class="text-[10px] text-mist-slate uppercase">Influence</div>
    </div>
  </InfoTooltip>
</div>
```

Add import:
```js
import { computed } from 'vue'
import { createAvatar } from '@dicebear/core'
import { personas } from '@dicebear/collection'
import { getEntityColor } from './graphColors.js'
import InfoTooltip from '../InfoTooltip.vue'
```

- [ ] **Step 3: Update GraphVisualization.vue hover tooltip**

Add import to the script section (after the existing imports at line 140):
```js
import { getTooltip } from '../../data/tooltipCopy.js'
```

Enhance the hover tooltip at lines 104-128. Add a meaning line after the stance:

```vue
<!-- Before (the closing part of the tooltip, lines 125-128): -->
<div v-if="hoveredNode.stance && hoveredNode.stance !== 'neutral'" class="mt-0.5 text-[11px] text-mist-drift capitalize">
  {{ hoveredNode.stance }}
</div>
</div>

<!-- After: -->
<div v-if="hoveredNode.stance && hoveredNode.stance !== 'neutral'" class="mt-0.5 text-[11px] text-mist-drift capitalize">
  {{ hoveredNode.stance }}
</div>
<div class="border-t mt-1.5 pt-1.5" style="border-color: rgba(34,211,238,0.1);">
  <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('graphVisualization.hoverMeaning')?.meaning }}</div>
</div>
</div>
```

Also update the tooltip styling at line 107 to match dark-glass:

```vue
<!-- Before: -->
class="absolute pointer-events-none z-20 bg-ocean-deep/95 backdrop-blur text-mist-foam text-xs rounded-lg px-3 py-2 border border-ocean-teal/30 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"

<!-- After: -->
class="absolute pointer-events-none z-20 text-mist-foam text-xs rounded-lg px-3 py-2 border"
style="background: rgba(10,20,30,0.92); border-color: rgba(34,211,238,0.2); box-shadow: 0 10px 40px rgba(8,47,73,0.3); max-width: 240px;"
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/graph/
git commit -m "feat: add tooltip explanations to Graph View components"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd frontend && npx vitest run`
Expected: all tests pass, including new InfoTooltip and tooltipCopy tests

- [ ] **Step 2: Run linter**

Run: `cd frontend && npx vue-tsc --noEmit 2>/dev/null; echo "done"` (if TypeScript configured)
Or: verify no console errors by checking build.

- [ ] **Step 3: Build check**

Run: `cd frontend && npm run build`
Expected: successful build with no errors

- [ ] **Step 4: Commit any fixes**

If any fixes were needed, commit them:
```bash
git add -A
git commit -m "fix: address tooltip integration build issues"
```
