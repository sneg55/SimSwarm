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
