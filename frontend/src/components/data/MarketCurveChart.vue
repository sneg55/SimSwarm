<template>
  <div v-for="market in markets" :key="market.market_id" class="bg-ocean-deep border border-mist-depth rounded-2xl p-5 mb-4">
    <div class="flex justify-between items-center mb-3">
      <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate">Prediction Market</div>
      <div class="text-xs text-mist-slate">
        {{ market.outcome_a }}: <InfoTooltip copyKey="marketCurveChart.currentPrice"><span class="text-green-400 font-mono">{{ currentPrice(market) }}%</span></InfoTooltip>
      </div>
    </div>
    <div class="text-sm text-mist-drift mb-4">{{ market.question }}</div>
    <div class="flex gap-4 text-xs text-mist-slate mb-2">
      <span><span class="inline-block w-3 h-0.5 bg-green-400 rounded mr-1 align-middle"></span>{{ market.outcome_a || 'YES' }}</span>
      <span><span class="inline-block w-3 h-0.5 bg-red-400 rounded mr-1 align-middle" style="border-bottom:1px dashed #F87171;"></span>{{ market.outcome_b || 'NO' }}</span>
    </div>
    <div class="relative" @mousemove="onHover($event, market)" @mouseleave="hovered = null">
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="overflow:visible;">
        <defs>
          <linearGradient :id="'gGrad-' + market.market_id" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#4ADE80" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="#4ADE80" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <line v-for="pct in [25, 50, 75]" :key="pct" :x1="PAD" :x2="W - PAD" :y1="yScale(pct)" :y2="yScale(pct)" stroke="#1E293B" stroke-dasharray="4" />
        <text v-for="pct in [0, 25, 50, 75, 100]" :key="'y'+pct" :x="PAD - 4" :y="yScale(pct) + 3" text-anchor="end" fill="#64748B" font-size="10">{{ pct }}%</text>
        <template v-if="(market.points || []).length > 1">
          <path :d="areaPath(market, 'yes')" :fill="`url(#gGrad-${market.market_id})`" />
          <path :d="linePath(market, 'yes')" fill="none" stroke="#4ADE80" stroke-width="2" />
          <path :d="linePath(market, 'no')" fill="none" stroke="#F87171" stroke-width="1.5" stroke-dasharray="6,3" />
        </template>
        <template v-else-if="(market.points || []).length === 1">
          <line :x1="PAD" :x2="W - PAD" :y1="yScale(market.points[0].price_yes * 100)" :y2="yScale(market.points[0].price_yes * 100)" stroke="#4ADE80" stroke-width="1.5" stroke-dasharray="6,3" />
          <circle :cx="(W - PAD * 2) / 2 + PAD" :cy="yScale(market.points[0].price_yes * 100)" r="5" fill="#4ADE80" stroke="#0B1426" stroke-width="2" />
          <text :x="(W - PAD * 2) / 2 + PAD" :y="yScale(market.points[0].price_yes * 100) - 12" text-anchor="middle" fill="#94A3B8" font-size="11">Only 1 trade</text>
        </template>
        <circle v-if="hovered && hovered.marketId === market.market_id" :cx="hovered.cx" :cy="hovered.cy" r="4" fill="#4ADE80" stroke="#0B1426" stroke-width="2" />
      </svg>
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
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import InfoTooltip from '../InfoTooltip.vue'
import { getTooltip } from '../../data/tooltipCopy.js'

const props = defineProps({
  markets: { type: Array, default: () => [] },
})

const W = 600
const H = 200
const PAD = 36
const hovered = ref(null)

function yScale(pct) { return PAD + (1 - pct / 100) * (H - PAD * 2) }
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

function areaPath(market) {
  const pts = market.points || []
  if (!pts.length) return ''
  const line = pts.map((p, i) => {
    const x = xScale(i, pts.length)
    const y = yScale(p.price_yes * 100)
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
  let closest = 0, minDist = Infinity
  for (let i = 0; i < pts.length; i++) {
    const d = Math.abs(xScale(i, pts.length) - svgX)
    if (d < minDist) { minDist = d; closest = i }
  }
  const p = pts[closest]
  hovered.value = {
    marketId: market.market_id,
    idx: p.trade_idx,
    cx: xScale(closest, pts.length),
    cy: yScale(p.price_yes * 100),
    x: (xScale(closest, pts.length) / W) * rect.width,
    y: (yScale(p.price_yes * 100) / H) * rect.height,
    yes: Math.round(p.price_yes * 100),
    no: Math.round(p.price_no * 100),
    vol: Math.round(p.volume),
  }
}
</script>
