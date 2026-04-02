# Frontend Data Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Data" dashboard tab with 7 visualization components + 2 compact Story view cards, rendering rich simulation data (market curves, agent trajectories, engagement, posts, social graph, trades, profiles) fetched from MinIO via presigned URLs.

**Architecture:** New `DataDashboard.vue` container fetches presigned download URLs from `GET /api/jobs/{id}/sim-data`, lazy-loads individual JSON files via IntersectionObserver, passes data as props to child components. All charts are custom SVG/Canvas — no charting library. ViewModeToggle updated to show 4th "Data" option conditionally when `sim_data_available` is true.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS, SVG (charts), Canvas (social graph)

**Spec:** `docs/superpowers/specs/2026-04-02-frontend-data-visualization-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/api/jobs.js` | Add `getSimData(jobId)` |
| Create | `frontend/src/components/data/MarketCurveChart.vue` | SVG market probability chart |
| Create | `frontend/src/components/data/AgentTrajectoryChart.vue` | SVG multi-line sentiment chart |
| Create | `frontend/src/components/data/EngagementChart.vue` | SVG stacked bar chart |
| Create | `frontend/src/components/data/TopPostsFeed.vue` | HTML post list |
| Create | `frontend/src/components/data/SocialGraphView.vue` | Canvas force graph |
| Create | `frontend/src/components/data/TradeFeed.vue` | HTML trade list |
| Create | `frontend/src/components/data/AgentProfileCards.vue` | HTML profile cards |
| Create | `frontend/src/components/data/DataDashboard.vue` | Container: fetch, lazy-load, grid layout |
| Create | `frontend/src/components/results/MarketCurveCompact.vue` | Compact sparkline for Story |
| Create | `frontend/src/components/results/EngagementCompact.vue` | Compact bar sparkline for Story |
| Modify | `frontend/src/components/ViewModeToggle.vue` | Add "Data" tab option |
| Modify | `frontend/src/views/SimulationResults.vue` | Wire Data tab + compact cards |

---

### Task 1: API client + Data tab toggle

**Files:**
- Modify: `frontend/src/api/jobs.js`
- Modify: `frontend/src/components/ViewModeToggle.vue`

- [ ] **Step 1: Add getSimData to API client**

In `frontend/src/api/jobs.js`, add after the `revokeShareLink` function:

```javascript
export async function getSimData(jobId) {
  const response = await api.get(`/jobs/${jobId}/sim-data`)
  return response.data
}
```

- [ ] **Step 2: Update ViewModeToggle to support conditional Data tab**

Replace `frontend/src/components/ViewModeToggle.vue`:

```vue
<template>
  <div class="inline-flex gap-0.5 bg-ocean-deep border border-mist-depth rounded-xl p-0.5">
    <button
      v-for="mode in availableModes"
      :key="mode.value"
      @click="$emit('update:modelValue', mode.value)"
      class="px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-250"
      :class="modelValue === mode.value
        ? 'bg-ocean-cyan/20 text-mist-foam'
        : 'text-mist-slate hover:text-mist-drift'"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: 'story' },
  compact: { type: Boolean, default: false },
  showData: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const baseModes = [
  { value: 'story', label: 'Story' },
  { value: 'graph', label: 'Graph' },
  { value: 'report', label: 'Report' },
]

const availableModes = computed(() => {
  const modes = [...baseModes]
  if (props.showData) {
    modes.splice(2, 0, { value: 'data', label: 'Data' })
  }
  if (props.compact) return modes.filter((m) => m.value !== 'dual')
  return modes
})
</script>
```

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 4: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/jobs.js frontend/src/components/ViewModeToggle.vue
git commit -m "feat: add getSimData API + Data tab in ViewModeToggle"
```

---

### Task 2: MarketCurveChart (SVG)

**Files:**
- Create: `frontend/src/components/data/MarketCurveChart.vue`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/data/MarketCurveChart.vue`:

```vue
<template>
  <div v-for="market in markets" :key="market.market_id" class="bg-ocean-deep border border-mist-depth rounded-2xl p-5 mb-4">
    <div class="flex justify-between items-center mb-3">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate">Prediction Market</div>
      <div class="text-xs text-mist-slate">
        {{ market.outcome_a }}: <span class="text-green-400 font-mono">{{ currentPrice(market) }}%</span>
      </div>
    </div>
    <div class="text-sm text-mist-drift mb-4">{{ market.question }}</div>

    <!-- Legend -->
    <div class="flex gap-4 text-xs text-mist-slate mb-2">
      <span><span class="inline-block w-3 h-0.5 bg-green-400 rounded mr-1 align-middle"></span>{{ market.outcome_a || 'YES' }}</span>
      <span><span class="inline-block w-3 h-0.5 bg-red-400 rounded mr-1 align-middle" style="border-bottom:1px dashed #F87171;"></span>{{ market.outcome_b || 'NO' }}</span>
    </div>

    <!-- Chart -->
    <div class="relative" @mousemove="onHover($event, market)" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="overflow:visible;">
        <defs>
          <linearGradient :id="'gGrad-' + market.market_id" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#4ADE80" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="#4ADE80" stop-opacity="0"/>
          </linearGradient>
        </defs>

        <!-- Grid lines -->
        <line v-for="pct in [25, 50, 75]" :key="pct"
          :x1="PAD" :x2="W - PAD" :y1="yScale(pct)" :y2="yScale(pct)"
          stroke="#1E293B" stroke-dasharray="4" />

        <!-- Y labels -->
        <text v-for="pct in [0, 25, 50, 75, 100]" :key="'y'+pct"
          :x="PAD - 4" :y="yScale(pct) + 3" text-anchor="end"
          fill="#64748B" font-size="10">{{ pct }}%</text>

        <!-- YES area fill -->
        <path :d="areaPath(market, 'yes')" :fill="`url(#gGrad-${market.market_id})`" />

        <!-- YES line (green solid) -->
        <path :d="linePath(market, 'yes')" fill="none" stroke="#4ADE80" stroke-width="2" />

        <!-- NO line (red dashed) -->
        <path :d="linePath(market, 'no')" fill="none" stroke="#F87171" stroke-width="1.5" stroke-dasharray="6,3" />

        <!-- Hover dot -->
        <circle v-if="hovered && hovered.marketId === market.market_id"
          :cx="hovered.x" :cy="hovered.y" r="4" fill="#4ADE80" stroke="#0B1426" stroke-width="2" />
      </svg>

      <!-- Tooltip -->
      <div v-if="hovered && hovered.marketId === market.market_id"
        class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs"
        :style="{ left: hovered.x + 'px', top: (hovered.y - 60) + 'px', transform: 'translateX(-50%)' }">
        <div class="text-mist-slate">Trade #{{ hovered.idx }}</div>
        <div><span class="text-green-400">YES: {{ hovered.yes }}%</span> · <span class="text-red-400">NO: {{ hovered.no }}%</span></div>
        <div class="text-mist-slate">Vol: ${{ hovered.vol }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  markets: { type: Array, default: () => [] },
})

const W = 600
const H = 200
const PAD = 36

const hovered = ref(null)

function yScale(pct) {
  return PAD + (1 - pct / 100) * (H - PAD * 2)
}

function xScale(idx, total) {
  if (total <= 1) return PAD + (W - PAD * 2) / 2
  return PAD + (idx / (total - 1)) * (W - PAD * 2)
}

function linePath(market, side) {
  const pts = market.points || []
  if (!pts.length) return ''
  return pts.map((p, i) => {
    const x = xScale(i, pts.length)
    const y = yScale((side === 'yes' ? p.price_yes : p.price_no) * 100)
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  }).join(' ')
}

function areaPath(market, side) {
  const pts = market.points || []
  if (!pts.length) return ''
  const line = pts.map((p, i) => {
    const x = xScale(i, pts.length)
    const y = yScale((side === 'yes' ? p.price_yes : p.price_no) * 100)
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  }).join(' ')
  const lastX = xScale(pts.length - 1, pts.length)
  const firstX = xScale(0, pts.length)
  const bottom = yScale(0)
  return `${line} L${lastX},${bottom} L${firstX},${bottom} Z`
}

function currentPrice(market) {
  const pts = market.points || []
  if (!pts.length) return '—'
  return Math.round(pts[pts.length - 1].price_yes * 100)
}

function onHover(e, market) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const svgX = (mouseX / rect.width) * W
  const pts = market.points || []
  if (!pts.length) return

  let closest = 0
  let minDist = Infinity
  for (let i = 0; i < pts.length; i++) {
    const x = xScale(i, pts.length)
    const d = Math.abs(x - svgX)
    if (d < minDist) { minDist = d; closest = i }
  }

  const p = pts[closest]
  hovered.value = {
    marketId: market.market_id,
    idx: p.trade_idx,
    x: (xScale(closest, pts.length) / W) * rect.width,
    y: (yScale(p.price_yes * 100) / H) * rect.height,
    yes: Math.round(p.price_yes * 100),
    no: Math.round(p.price_no * 100),
    vol: Math.round(p.volume),
  }
}
</script>
```

- [ ] **Step 2: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/data/MarketCurveChart.vue
git commit -m "feat: add MarketCurveChart SVG component (green YES / red NO)"
```

---

### Task 3: AgentTrajectoryChart + EngagementChart (SVG)

**Files:**
- Create: `frontend/src/components/data/AgentTrajectoryChart.vue`
- Create: `frontend/src/components/data/EngagementChart.vue`

- [ ] **Step 1: Create AgentTrajectoryChart**

Create `frontend/src/components/data/AgentTrajectoryChart.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Agent Sentiment Over Time</div>

    <div class="relative" @mousemove="onHover" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="overflow:visible;">
        <!-- Grid -->
        <line :x1="PAD" :x2="W-PAD" :y1="yScale(0)" :y2="yScale(0)" stroke="#1E293B" stroke-dasharray="4" />
        <text :x="PAD-4" :y="yScale(1)+3" text-anchor="end" fill="#64748B" font-size="10">+1</text>
        <text :x="PAD-4" :y="yScale(0)+3" text-anchor="end" fill="#64748B" font-size="10">0</text>
        <text :x="PAD-4" :y="yScale(-1)+3" text-anchor="end" fill="#64748B" font-size="10">-1</text>

        <!-- Agent lines -->
        <path v-for="agent in agents" :key="agent.agent_id"
          :d="agentPath(agent)" fill="none" :stroke="agentColor(agent)" stroke-width="1.5" opacity="0.7" />
      </svg>

      <!-- Tooltip -->
      <div v-if="hovered"
        class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs z-10"
        :style="{ left: hovered.x + 'px', top: '8px' }">
        <div class="text-mist-foam font-medium">{{ hovered.name }}</div>
        <div class="text-mist-slate">Round {{ hovered.round }} · {{ hovered.posts }} posts</div>
        <div :style="{ color: hovered.sentiment >= 0 ? '#4ADE80' : '#F87171' }">
          Sentiment: {{ hovered.sentiment > 0 ? '+' : '' }}{{ hovered.sentiment }}
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="flex flex-wrap gap-3 mt-3">
      <span v-for="agent in agents.slice(0, 10)" :key="agent.agent_id" class="text-[10px] text-mist-slate flex items-center gap-1">
        <span class="inline-block w-2 h-2 rounded-full" :style="{ background: agentColor(agent) }"></span>
        {{ agent.name }}
      </span>
      <span v-if="agents.length > 10" class="text-[10px] text-mist-slate">+{{ agents.length - 10 }} more</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'

const props = defineProps({
  agents: { type: Array, default: () => [] },
})

const W = 600
const H = 180
const PAD = 36

const hovered = ref(null)

function yScale(val) {
  return PAD + (1 - (val + 1) / 2) * (H - PAD * 2)
}

function xScale(idx, total) {
  if (total <= 1) return PAD + (W - PAD * 2) / 2
  return PAD + (idx / (total - 1)) * (W - PAD * 2)
}

function agentColor(agent) {
  return getEntityColor(agent.type || agent.name || 'Entity')
}

function agentPath(agent) {
  const rounds = agent.rounds || []
  if (!rounds.length) return ''
  return rounds.map((r, i) => {
    const x = xScale(i, rounds.length)
    const y = yScale(r.sentiment || 0)
    return `${i === 0 ? 'M' : 'L'}${x},${y}`
  }).join(' ')
}

function onHover(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const svgX = (mouseX / rect.width) * W
  if (!props.agents.length) return

  const firstAgent = props.agents[0]
  const rounds = firstAgent.rounds || []
  if (!rounds.length) return

  let closestIdx = 0
  let minDist = Infinity
  for (let i = 0; i < rounds.length; i++) {
    const d = Math.abs(xScale(i, rounds.length) - svgX)
    if (d < minDist) { minDist = d; closestIdx = i }
  }

  // Find agent with highest absolute sentiment at this round
  let best = props.agents[0]
  let bestAbs = 0
  for (const a of props.agents) {
    const s = Math.abs((a.rounds[closestIdx]?.sentiment) || 0)
    if (s > bestAbs) { bestAbs = s; best = a }
  }

  const r = best.rounds[closestIdx]
  hovered.value = {
    x: (xScale(closestIdx, rounds.length) / W) * rect.width,
    name: best.name,
    round: r?.round ?? closestIdx,
    posts: r?.posts ?? 0,
    sentiment: r?.sentiment?.toFixed(2) ?? '0.00',
  }
}
</script>
```

- [ ] **Step 2: Create EngagementChart**

Create `frontend/src/components/data/EngagementChart.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Activity Over Time</div>

    <div class="relative" @mousemove="onHover" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full">
        <g v-for="(entry, i) in data" :key="i">
          <!-- Posts bar -->
          <rect :x="barX(i)" :y="yScale(entry.total_posts + entry.total_likes + entry.total_comments)"
            :width="barW" :height="barH(entry.total_posts + entry.total_likes + entry.total_comments)"
            fill="#22D3EE" opacity="0.8" rx="2" />
          <!-- Likes bar (stacked) -->
          <rect :x="barX(i)" :y="yScale(entry.total_likes + entry.total_comments)"
            :width="barW" :height="barH(entry.total_likes + entry.total_comments)"
            fill="#6EE7B7" opacity="0.8" rx="2" />
          <!-- Comments bar (bottom) -->
          <rect :x="barX(i)" :y="yScale(entry.total_comments)"
            :width="barW" :height="barH(entry.total_comments)"
            fill="#A78BFA" opacity="0.8" rx="2" />
        </g>
      </svg>

      <!-- Tooltip -->
      <div v-if="hovered"
        class="absolute pointer-events-none bg-ocean-abyss border border-mist-depth rounded-lg px-3 py-2 text-xs z-10"
        :style="{ left: hovered.x + 'px', top: '8px' }">
        <div class="text-mist-slate">Round {{ hovered.round }}</div>
        <div><span style="color:#22D3EE;">Posts: {{ hovered.posts }}</span></div>
        <div><span style="color:#6EE7B7;">Likes: {{ hovered.likes }}</span></div>
        <div><span style="color:#A78BFA;">Comments: {{ hovered.comments }}</span></div>
        <div class="text-mist-slate">{{ hovered.agents }} active agents</div>
      </div>
    </div>

    <!-- Legend -->
    <div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#22D3EE] mr-1 align-middle"></span>Posts</span>
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#6EE7B7] mr-1 align-middle"></span>Likes</span>
      <span><span class="inline-block w-2 h-2 rounded-sm bg-[#A78BFA] mr-1 align-middle"></span>Comments</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const W = 600
const H = 140
const PAD = 8

const hovered = ref(null)

const maxVal = computed(() => {
  let m = 1
  for (const e of props.data) {
    const total = (e.total_posts || 0) + (e.total_likes || 0) + (e.total_comments || 0)
    if (total > m) m = total
  }
  return m
})

const barW = computed(() => {
  if (!props.data.length) return 0
  return Math.max(2, (W - PAD * 2) / props.data.length - 2)
})

function barX(i) {
  if (!props.data.length) return 0
  return PAD + (i / props.data.length) * (W - PAD * 2)
}

function yScale(val) {
  return H - PAD - (val / maxVal.value) * (H - PAD * 2)
}

function barH(val) {
  return (val / maxVal.value) * (H - PAD * 2)
}

function onHover(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const idx = Math.floor((mouseX / rect.width) * props.data.length)
  if (idx < 0 || idx >= props.data.length) return
  const entry = props.data[idx]
  hovered.value = {
    x: mouseX,
    round: entry.round,
    posts: entry.total_posts,
    likes: entry.total_likes,
    comments: entry.total_comments,
    agents: entry.active_agents,
  }
}
</script>
```

- [ ] **Step 3: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/data/AgentTrajectoryChart.vue frontend/src/components/data/EngagementChart.vue
git commit -m "feat: add AgentTrajectoryChart + EngagementChart SVG components"
```

---

### Task 4: TopPostsFeed + TradeFeed + AgentProfileCards (HTML/Tailwind)

**Files:**
- Create: `frontend/src/components/data/TopPostsFeed.vue`
- Create: `frontend/src/components/data/TradeFeed.vue`
- Create: `frontend/src/components/data/AgentProfileCards.vue`

- [ ] **Step 1: Create TopPostsFeed**

Create `frontend/src/components/data/TopPostsFeed.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Top Posts</div>
    <div class="space-y-1 max-h-[400px] overflow-y-auto">
      <div v-for="post in posts" :key="post.post_id + post.platform"
        class="flex gap-3 p-3 rounded-xl hover:bg-ocean-abyss/50 transition-colors">
        <div class="flex-shrink-0 text-sm">{{ post.platform === 'twitter' ? '𝕏' : '📱' }}</div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-medium text-ocean-cyan truncate">{{ post.agent_name }}</span>
            <span class="text-[10px] text-mist-slate">{{ post.platform }}</span>
          </div>
          <p class="text-xs text-mist-drift leading-relaxed line-clamp-3">{{ post.content }}</p>
          <div class="flex gap-3 mt-1.5 text-[10px] text-mist-slate">
            <span v-if="post.num_likes" class="text-green-400">♥ {{ post.num_likes }}</span>
            <span v-if="post.num_shares">↻ {{ post.num_shares }}</span>
            <span v-if="post.num_dislikes" class="text-red-400">↓ {{ post.num_dislikes }}</span>
          </div>
        </div>
      </div>
      <div v-if="!posts.length" class="text-xs text-mist-slate text-center py-8">No posts available</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  posts: { type: Array, default: () => [] },
})
</script>
```

- [ ] **Step 2: Create TradeFeed**

Create `frontend/src/components/data/TradeFeed.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Trades</div>
    <div class="space-y-1 max-h-[400px] overflow-y-auto">
      <div v-for="trade in trades" :key="trade.trade_id"
        class="flex items-center gap-3 p-2 rounded-lg hover:bg-ocean-abyss/50 transition-colors text-xs">
        <span :class="trade.side === 'buy' ? 'text-green-400' : 'text-red-400'" class="font-mono font-bold w-8">
          {{ trade.side === 'buy' ? 'BUY' : 'SELL' }}
        </span>
        <span class="text-ocean-cyan truncate flex-1">{{ trade.agent_name }}</span>
        <span class="text-mist-drift">{{ trade.outcome }}</span>
        <span class="text-mist-slate font-mono">@ {{ (trade.price * 100).toFixed(0) }}%</span>
        <span class="text-mist-slate font-mono">${{ Math.round(trade.cost) }}</span>
      </div>
      <div v-if="!trades.length" class="text-xs text-mist-slate text-center py-8">No trades available</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  trades: { type: Array, default: () => [] },
})
</script>
```

- [ ] **Step 3: Create AgentProfileCards**

Create `frontend/src/components/data/AgentProfileCards.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Agent Profiles</div>
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="(profile, i) in profiles" :key="i"
        class="bg-ocean-abyss border border-mist-depth rounded-xl p-3">
        <div class="text-sm font-medium text-mist-foam truncate">{{ profile.name || profile.user_name || 'Agent' }}</div>
        <div v-if="profile.persona || profile.bio" class="text-[11px] text-mist-slate mt-1 line-clamp-3">
          {{ profile.persona || profile.bio }}
        </div>
        <div class="flex gap-2 mt-2 text-[10px] text-mist-slate">
          <span v-if="profile.mbti" class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.mbti }}</span>
          <span v-if="profile.country" class="px-1.5 py-0.5 bg-ocean-deep rounded">{{ profile.country }}</span>
        </div>
      </div>
      <div v-if="!profiles.length" class="col-span-full text-xs text-mist-slate text-center py-8">No profiles available</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  profiles: { type: Array, default: () => [] },
})
</script>
```

- [ ] **Step 4: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/data/TopPostsFeed.vue frontend/src/components/data/TradeFeed.vue frontend/src/components/data/AgentProfileCards.vue
git commit -m "feat: add TopPostsFeed, TradeFeed, AgentProfileCards components"
```

---

### Task 5: SocialGraphView (Canvas)

**Files:**
- Create: `frontend/src/components/data/SocialGraphView.vue`

- [ ] **Step 1: Create SocialGraphView**

Create `frontend/src/components/data/SocialGraphView.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Social Graph</div>
    <div ref="containerRef" class="relative" style="height: 300px;">
      <canvas ref="canvasRef" class="w-full h-full" style="display:block;" />
    </div>
    <div class="flex gap-4 mt-2 text-[10px] text-mist-slate">
      <span>Nodes = agents · Edges = follows · <span class="text-ocean-cyan">Bright edges</span> = mutual follows</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'

const props = defineProps({
  graph: { type: Object, default: () => ({ edges: [], mutual_follows: [] }) },
})

const containerRef = ref(null)
const canvasRef = ref(null)

let ctx = null
let W = 0, H = 0
let nodes = []
let edges = []
let mutualSet = new Set()
let animFrame = null

function setup() {
  if (!canvasRef.value || !containerRef.value) return
  W = containerRef.value.clientWidth
  H = containerRef.value.clientHeight
  const dpr = window.devicePixelRatio || 1
  canvasRef.value.width = W * dpr
  canvasRef.value.height = H * dpr
  canvasRef.value.style.width = W + 'px'
  canvasRef.value.style.height = H + 'px'
  ctx = canvasRef.value.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function buildGraph() {
  const gEdges = props.graph.edges || []
  const mutual = props.graph.mutual_follows || []

  // Collect unique agents
  const agentMap = {}
  for (const e of gEdges) {
    if (!agentMap[e.follower_id]) agentMap[e.follower_id] = { id: e.follower_id, name: e.follower_name, followers: 0 }
    if (!agentMap[e.followee_id]) agentMap[e.followee_id] = { id: e.followee_id, name: e.followee_name, followers: 0 }
    agentMap[e.followee_id].followers++
  }

  nodes = Object.values(agentMap).map((a, i) => ({
    ...a,
    x: W / 2 + (Math.random() - 0.5) * W * 0.6,
    y: H / 2 + (Math.random() - 0.5) * H * 0.6,
    vx: 0, vy: 0,
    size: 3 + Math.sqrt(a.followers + 1) * 2,
    color: getEntityColor(a.name || 'Entity'),
  }))

  const nodeIdx = {}
  nodes.forEach((n, i) => { nodeIdx[n.id] = i })
  edges = gEdges.map(e => ({ from: nodeIdx[e.follower_id], to: nodeIdx[e.followee_id] })).filter(e => e.from !== undefined && e.to !== undefined)

  mutualSet = new Set()
  for (const m of mutual) {
    mutualSet.add(`${Math.min(m.agent_a, m.agent_b)}-${Math.max(m.agent_a, m.agent_b)}`)
  }
}

function isMutual(a, b) {
  return mutualSet.has(`${Math.min(a, b)}-${Math.max(a, b)}`)
}

function animate() {
  if (!ctx) { animFrame = requestAnimationFrame(animate); return }
  ctx.clearRect(0, 0, W, H)

  // Physics
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i]
    n.vx += (W / 2 - n.x) * 0.0001
    n.vy += (H / 2 - n.y) * 0.0001
    for (let j = i + 1; j < nodes.length; j++) {
      const m = nodes[j]
      const dx = m.x - n.x, dy = m.y - n.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < 60 && d > 0.5) {
        const f = 0.15 * (1 - d / 60)
        n.vx -= (dx / d) * f; n.vy -= (dy / d) * f
        m.vx += (dx / d) * f; m.vy += (dy / d) * f
      }
    }
    n.vx *= 0.95; n.vy *= 0.95
    n.x += n.vx; n.y += n.vy
    n.x = Math.max(10, Math.min(W - 10, n.x))
    n.y = Math.max(10, Math.min(H - 10, n.y))
  }

  // Edges
  for (const e of edges) {
    const a = nodes[e.from], b = nodes[e.to]
    if (!a || !b) continue
    const mutual = isMutual(a.id, b.id)
    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    ctx.strokeStyle = mutual ? 'rgba(34,211,238,0.4)' : 'rgba(30,41,59,0.3)'
    ctx.lineWidth = mutual ? 1.5 : 0.5
    ctx.stroke()
  }

  // Nodes
  for (const n of nodes) {
    ctx.beginPath()
    ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2)
    ctx.fillStyle = n.color
    ctx.globalAlpha = 0.8
    ctx.fill()
    ctx.globalAlpha = 1

    if (n.size > 5) {
      ctx.font = '9px Inter'
      ctx.fillStyle = 'rgba(241,245,249,0.5)'
      ctx.textAlign = 'center'
      ctx.fillText(n.name, n.x, n.y + n.size + 10)
    }
  }

  animFrame = requestAnimationFrame(animate)
}

watch(() => props.graph, () => { buildGraph() }, { deep: true })

onMounted(() => {
  nextTick(() => {
    setup()
    buildGraph()
    animFrame = requestAnimationFrame(animate)
  })
})

onBeforeUnmount(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
})
</script>
```

- [ ] **Step 2: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/data/SocialGraphView.vue
git commit -m "feat: add SocialGraphView canvas component with force layout"
```

---

### Task 6: DataDashboard container

**Files:**
- Create: `frontend/src/components/data/DataDashboard.vue`

- [ ] **Step 1: Create DataDashboard**

Create `frontend/src/components/data/DataDashboard.vue`:

```vue
<template>
  <div class="pt-[80px] pb-24 px-4 md:px-8">
    <div class="max-w-[960px] mx-auto">
      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="text-mist-slate text-sm">Loading simulation data…</div>
      </div>
      <div v-else-if="error" class="flex items-center justify-center py-20">
        <div class="text-mist-slate text-sm">{{ error }}</div>
      </div>
      <template v-else>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Market curves — full width -->
          <div class="md:col-span-2">
            <MarketCurveChart :markets="marketCurves" />
          </div>

          <!-- Agent trajectories — left -->
          <AgentTrajectoryChart :agents="agentTrajectories" />

          <!-- Engagement — right -->
          <EngagementChart :data="engagementSummary" />

          <!-- Top posts — left -->
          <TopPostsFeed :posts="topPosts" />

          <!-- Social graph — right -->
          <SocialGraphView :graph="socialGraph" />

          <!-- Trades — full width -->
          <div class="md:col-span-2">
            <TradeFeed :trades="trades" />
          </div>

          <!-- Profiles — full width -->
          <div class="md:col-span-2">
            <AgentProfileCards :profiles="profiles" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSimData } from '../../api/jobs.js'
import MarketCurveChart from './MarketCurveChart.vue'
import AgentTrajectoryChart from './AgentTrajectoryChart.vue'
import EngagementChart from './EngagementChart.vue'
import TopPostsFeed from './TopPostsFeed.vue'
import SocialGraphView from './SocialGraphView.vue'
import TradeFeed from './TradeFeed.vue'
import AgentProfileCards from './AgentProfileCards.vue'

const props = defineProps({
  jobId: { type: [String, Number], required: true },
})

const loading = ref(true)
const error = ref(null)

const marketCurves = ref([])
const agentTrajectories = ref([])
const engagementSummary = ref([])
const topPosts = ref([])
const socialGraph = ref({ edges: [], mutual_follows: [] })
const trades = ref([])
const profiles = ref([])

async function fetchFile(url) {
  const resp = await fetch(url)
  if (!resp.ok) return null
  return resp.json()
}

onMounted(async () => {
  try {
    const { files } = await getSimData(props.jobId)

    // Fetch chart-ready files first (small, above the fold)
    const [mc, at, es, tp] = await Promise.all([
      fetchFile(files['market_curves.json']),
      fetchFile(files['agent_trajectories.json']),
      fetchFile(files['engagement_summary.json']),
      fetchFile(files['top_posts.json']),
    ])
    marketCurves.value = mc || []
    agentTrajectories.value = at || []
    engagementSummary.value = es || []
    topPosts.value = tp || []

    // Fetch bulk files (below the fold, can load slightly later)
    const [sg, tr, pr] = await Promise.all([
      fetchFile(files['social_graph.json']),
      fetchFile(files['trades.json']),
      fetchFile(files['profiles.json']),
    ])
    socialGraph.value = sg || { edges: [], mutual_follows: [] }
    trades.value = tr || []
    profiles.value = pr || []
  } catch (err) {
    error.value = 'Simulation data not available.'
    console.error('Failed to load sim data:', err)
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/data/DataDashboard.vue
git commit -m "feat: add DataDashboard container with grid layout and lazy loading"
```

---

### Task 7: Compact Story cards

**Files:**
- Create: `frontend/src/components/results/MarketCurveCompact.vue`
- Create: `frontend/src/components/results/EngagementCompact.vue`

- [ ] **Step 1: Create MarketCurveCompact**

Create `frontend/src/components/results/MarketCurveCompact.vue`:

```vue
<template>
  <div v-if="market" class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="flex justify-between items-center mb-2">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate">Prediction Market</div>
      <div class="text-xs font-mono">
        <span class="text-green-400">{{ currentYes }}%</span> YES
      </div>
    </div>
    <div class="text-xs text-mist-drift mb-3 line-clamp-1">{{ market.question }}</div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="w-full">
      <path :d="yesPath" fill="none" stroke="#4ADE80" stroke-width="2" />
      <path :d="noPath" fill="none" stroke="#F87171" stroke-width="1" stroke-dasharray="4,2" />
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  markets: { type: Array, default: () => [] },
})

const W = 300
const H = 50

const market = computed(() => props.markets[0] || null)

function yS(pct) { return (1 - pct) * H }
function xS(i, total) { return total <= 1 ? W / 2 : (i / (total - 1)) * W }

const yesPath = computed(() => {
  const pts = market.value?.points || []
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xS(i, pts.length)},${yS(p.price_yes)}`).join(' ')
})

const noPath = computed(() => {
  const pts = market.value?.points || []
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xS(i, pts.length)},${yS(p.price_no)}`).join(' ')
})

const currentYes = computed(() => {
  const pts = market.value?.points || []
  if (!pts.length) return '—'
  return Math.round(pts[pts.length - 1].price_yes * 100)
})
</script>
```

- [ ] **Step 2: Create EngagementCompact**

Create `frontend/src/components/results/EngagementCompact.vue`:

```vue
<template>
  <div v-if="data.length" class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="flex justify-between items-center mb-2">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate">Simulation Activity</div>
      <div class="text-xs text-mist-slate">{{ totalPosts }} posts · {{ totalLikes }} likes</div>
    </div>
    <div class="flex items-end gap-px" style="height: 40px;">
      <div v-for="(entry, i) in data" :key="i"
        class="flex-1 bg-ocean-cyan rounded-t-sm transition-all"
        :style="{ height: barHeight(entry) + '%', opacity: 0.5 + (barHeight(entry) / 200) }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const maxTotal = computed(() => {
  let m = 1
  for (const e of props.data) {
    const t = (e.total_posts || 0) + (e.total_likes || 0)
    if (t > m) m = t
  }
  return m
})

const totalPosts = computed(() => props.data.reduce((s, e) => s + (e.total_posts || 0), 0))
const totalLikes = computed(() => props.data.reduce((s, e) => s + (e.total_likes || 0), 0))

function barHeight(entry) {
  const t = (entry.total_posts || 0) + (entry.total_likes || 0)
  return Math.max(2, (t / maxTotal.value) * 100)
}
</script>
```

- [ ] **Step 3: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/results/MarketCurveCompact.vue frontend/src/components/results/EngagementCompact.vue
git commit -m "feat: add compact MarketCurve + Engagement sparklines for Story view"
```

---

### Task 8: Wire everything into SimulationResults

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Add imports**

In `frontend/src/views/SimulationResults.vue`, add imports in the `<script setup>` block (after existing imports):

```javascript
import DataDashboard from '../components/data/DataDashboard.vue'
import MarketCurveCompact from '../components/results/MarketCurveCompact.vue'
import EngagementCompact from '../components/results/EngagementCompact.vue'
import { getSimData } from '../api/jobs.js'
```

- [ ] **Step 2: Add sim data state**

After the existing `hasGraph` ref, add:

```javascript
const simDataAvailable = ref(false)
const simDataFiles = ref(null)
const compactMarkets = ref([])
const compactEngagement = ref([])
```

- [ ] **Step 3: Fetch sim data on mount**

In the `onMounted` callback, after `await fetchGraphData()`, add:

```javascript
    // Check for rich simulation data
    simDataAvailable.value = job.value?.sim_data_available || false
    if (simDataAvailable.value) {
      try {
        const sd = await getSimData(jobId)
        simDataFiles.value = sd.files
        // Fetch compact chart data
        const [mc, es] = await Promise.all([
          fetch(sd.files['market_curves.json']).then(r => r.ok ? r.json() : []),
          fetch(sd.files['engagement_summary.json']).then(r => r.ok ? r.json() : []),
        ])
        compactMarkets.value = mc || []
        compactEngagement.value = es || []
      } catch (err) {
        console.warn('Sim data not available:', err)
        simDataAvailable.value = false
      }
    }
```

- [ ] **Step 4: Pass showData to ResultsToolbar**

Update the `ResultsToolbar` in the template. The toolbar renders `ViewModeToggle` internally. We need to pass `showData` through. First check how ResultsToolbar passes props to ViewModeToggle.

In `ResultsToolbar.vue`, the toggle is rendered as:
```html
<ViewModeToggle v-if="showToggle" :modelValue="viewMode" @update:modelValue="..." />
```

Add `showData` prop to ResultsToolbar and pass through. In `frontend/src/components/results/ResultsToolbar.vue`, add `showData` to props:

```javascript
defineProps({
  title: { type: String, default: 'Results' },
  viewMode: { type: String, default: 'story' },
  showToggle: { type: Boolean, default: true },
  showData: { type: Boolean, default: false },
  backLink: { type: String, default: '/dashboard' },
  backLabel: { type: String, default: 'Dashboard' },
})
```

And pass it to ViewModeToggle:
```html
<ViewModeToggle v-if="showToggle" :modelValue="viewMode" :showData="showData" @update:modelValue="$emit('update:viewMode', $event)" />
```

Then in `SimulationResults.vue`, update the toolbar:
```html
    <ResultsToolbar
      :title="job?.goal || 'Results'"
      :viewMode="viewMode"
      :showToggle="true"
      :showData="simDataAvailable"
      @update:viewMode="viewMode = $event"
    />
```

- [ ] **Step 5: Add compact cards to Story view**

In the Story view template, after the coalitions section and before the `<ReportViewer>`, add:

```html
              <!-- Compact simulation data cards -->
              <div v-if="simDataAvailable" class="grid gap-4 md:grid-cols-2 mb-8" data-reveal>
                <MarketCurveCompact :markets="compactMarkets" />
                <EngagementCompact :data="compactEngagement" />
              </div>
```

- [ ] **Step 6: Add Data view to template**

After the Graph view `</div>` and before the Report view `<div v-else`, add:

```html
      <!-- ── Data View ── -->
      <div v-else-if="viewMode === 'data'" class="overflow-hidden" style="min-height: calc(100vh - 140px)">
        <DataDashboard :jobId="jobId" />
      </div>
```

Update the Report view condition from `v-else` to `v-else-if="viewMode === 'report'"` to avoid it catching the data view:

Change:
```html
      <!-- ── Report View ── -->
      <div v-else class="relative pt-[120px] pb-24">
```
To:
```html
      <!-- ── Report View ── -->
      <div v-else-if="viewMode === 'report'" class="relative pt-[120px] pb-24">
```

- [ ] **Step 7: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 8: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/SimulationResults.vue frontend/src/components/results/ResultsToolbar.vue
git commit -m "feat: wire Data dashboard + compact cards into SimulationResults"
```

---

### Task 9: Full test suite + build verification

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npx vite build`
Expected: Build succeeds
