<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Agent Sentiment Over Time</div>
    <div v-if="!hasData" class="flex items-center justify-center py-12 text-xs text-mist-slate">
      Insufficient sentiment data — agents posted too few opinion words to track shifts.
    </div>
    <div v-else class="relative" @mousemove="onHover" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="overflow:visible;">
        <line :x1="PAD" :x2="W-PAD" :y1="yScale(0)" :y2="yScale(0)" stroke="#1E293B" stroke-dasharray="4" />
        <text :x="PAD-4" :y="yScale(yRange)+3" text-anchor="end" fill="#64748B" font-size="10">{{ axisLabel(yRange) }}</text>
        <text :x="PAD-4" :y="yScale(0)+3" text-anchor="end" fill="#64748B" font-size="10">0</text>
        <text :x="PAD-4" :y="yScale(-yRange)+3" text-anchor="end" fill="#64748B" font-size="10">{{ axisLabel(-yRange) }}</text>
        <template v-for="agent in orderedAgents" :key="agent.agent_id">
          <path v-if="(agent.rounds || []).length > 1"
            :d="agentPath(agent)" fill="none"
            :stroke="agentColor(agent)"
            :stroke-width="strokeWidth(agent)"
            :opacity="lineOpacity(agent)" />
          <circle v-else-if="(agent.rounds || []).length === 1"
            :cx="xScale(0, 1)" :cy="yScale(agent.rounds[0].sentiment || 0)"
            :r="agent.agent_id === hoveredId ? 5 : 4"
            :fill="agentColor(agent)"
            :opacity="lineOpacity(agent)" />
        </template>
      </svg>
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
    </div>
    <div v-if="hasData" class="flex flex-wrap gap-3 mt-3">
      <span v-for="agent in agents.slice(0, 10)" :key="agent.agent_id"
            class="text-[11px] text-mist-slate flex items-center gap-1.5 cursor-pointer transition-colors hover:text-mist-foam"
            :class="{ 'text-mist-foam': hoveredId === agent.agent_id }"
            @mouseenter="hoveredId = agent.agent_id"
            @mouseleave="hoveredId = null">
        <span class="inline-block w-2.5 h-2.5 rounded-full transition-transform"
              :class="{ 'scale-125 ring-1 ring-mist-foam/40': hoveredId === agent.agent_id }"
              :style="{ background: agentColor(agent) }"></span>
        {{ agent.name }}
      </span>
      <span v-if="agents.length > 10" class="text-[11px] text-mist-slate">+{{ agents.length - 10 }} more</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getTooltip } from '../../data/tooltipCopy.js'

const props = defineProps({
  agents: { type: Array, default: () => [] },
})

const W = 600
const H = 180
const PAD = 36
const hovered = ref(null)
const hoveredId = ref(null)

// Stable per-agent color: evenly-spread HSL hues so 10+ agents stay distinct.
// Indexed off the agents prop so the legend dot and chart line always match.
const colorMap = computed(() => {
  const map = new Map()
  const n = props.agents.length || 1
  // Start at hue 180 (cyan) so the chart anchors in the app's ocean palette.
  props.agents.forEach((a, i) => {
    const hue = Math.round((180 + (i * 360) / n) % 360)
    map.set(a.agent_id, `hsl(${hue}, 68%, 62%)`)
  })
  return map
})

// Render the hovered agent last so its line draws on top of the dimmed others.
const orderedAgents = computed(() => {
  if (!hoveredId.value) return props.agents
  return [...props.agents].sort((a, b) => {
    const aH = a.agent_id === hoveredId.value ? 1 : 0
    const bH = b.agent_id === hoveredId.value ? 1 : 0
    return aH - bH
  })
})

const hasData = computed(() => {
  for (const a of props.agents) {
    for (const r of (a.rounds || [])) {
      if (r.sentiment && r.sentiment !== 0) return true
    }
  }
  return false
})

const yRange = computed(() => {
  let max = 0
  for (const a of props.agents) {
    for (const r of (a.rounds || [])) {
      const v = Math.abs(Number(r.sentiment) || 0)
      if (v > max) max = v
    }
  }
  if (max === 0) return 1
  // Pad by 20% so lines don't touch the frame, round up to a nice step.
  const padded = max * 1.2
  const steps = [0.1, 0.2, 0.25, 0.5, 0.75, 1]
  for (const s of steps) if (padded <= s) return s
  return 1
})

function axisLabel(v) {
  const sign = v > 0 ? '+' : v < 0 ? '-' : ''
  const abs = Math.abs(v)
  const str = abs >= 1 ? abs.toFixed(0) : abs.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')
  return `${sign}${str}`
}

function yScale(val) {
  const r = yRange.value
  const clamped = Math.max(-r, Math.min(r, val))
  return PAD + (1 - (clamped + r) / (2 * r)) * (H - PAD * 2)
}
function xScale(idx, total) {
  if (total <= 1) return PAD + (W - PAD * 2) / 2
  return PAD + (idx / (total - 1)) * (W - PAD * 2)
}
function agentColor(agent) { return colorMap.value.get(agent.agent_id) || 'hsl(180, 68%, 62%)' }

function lineOpacity(agent) {
  if (!hoveredId.value) return 0.7
  return agent.agent_id === hoveredId.value ? 1.0 : 0.12
}

function strokeWidth(agent) {
  return agent.agent_id === hoveredId.value ? 2.5 : 1.5
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
  let closestIdx = 0, minDist = Infinity
  for (let i = 0; i < rounds.length; i++) {
    const d = Math.abs(xScale(i, rounds.length) - svgX)
    if (d < minDist) { minDist = d; closestIdx = i }
  }
  let best = props.agents[0], bestAbs = 0
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
