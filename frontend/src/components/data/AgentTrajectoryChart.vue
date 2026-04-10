<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">Agent Sentiment Over Time</div>
    <div v-if="!hasData" class="flex items-center justify-center py-12 text-xs text-mist-slate">
      Insufficient sentiment data — agents posted too few opinion words to track shifts.
    </div>
    <div v-else class="relative" @mousemove="onHover" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="overflow:visible;">
        <line :x1="PAD" :x2="W-PAD" :y1="yScale(0)" :y2="yScale(0)" stroke="#1E293B" stroke-dasharray="4" />
        <text :x="PAD-4" :y="yScale(1)+3" text-anchor="end" fill="#64748B" font-size="10">+1</text>
        <text :x="PAD-4" :y="yScale(0)+3" text-anchor="end" fill="#64748B" font-size="10">0</text>
        <text :x="PAD-4" :y="yScale(-1)+3" text-anchor="end" fill="#64748B" font-size="10">-1</text>
        <template v-for="agent in agents" :key="agent.agent_id">
          <path v-if="(agent.rounds || []).length > 1"
            :d="agentPath(agent)" fill="none" :stroke="agentColor(agent)" stroke-width="1.5" opacity="0.7" />
          <circle v-else-if="(agent.rounds || []).length === 1"
            :cx="xScale(0, 1)" :cy="yScale(agent.rounds[0].sentiment || 0)" r="4"
            :fill="agentColor(agent)" opacity="0.8" />
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
      <span v-for="agent in agents.slice(0, 10)" :key="agent.agent_id" class="text-[10px] text-mist-slate flex items-center gap-1">
        <span class="inline-block w-2 h-2 rounded-full" :style="{ background: agentColor(agent) }"></span>
        {{ agent.name }}
      </span>
      <span v-if="agents.length > 10" class="text-[10px] text-mist-slate">+{{ agents.length - 10 }} more</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getEntityColor } from '../graph/graphColors.js'
import { getTooltip } from '../../data/tooltipCopy.js'

const props = defineProps({
  agents: { type: Array, default: () => [] },
})

const W = 600
const H = 180
const PAD = 36
const hovered = ref(null)

const hasData = computed(() => {
  for (const a of props.agents) {
    for (const r of (a.rounds || [])) {
      if (r.sentiment && r.sentiment !== 0) return true
    }
  }
  return false
})

function yScale(val) { return PAD + (1 - (val + 1) / 2) * (H - PAD * 2) }
function xScale(idx, total) {
  if (total <= 1) return PAD + (W - PAD * 2) / 2
  return PAD + (idx / (total - 1)) * (W - PAD * 2)
}
function agentColor(agent) { return getEntityColor(agent.type || agent.name || 'Entity') }
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
