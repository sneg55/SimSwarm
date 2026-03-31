<template>
  <div class="mt-3">
    <!-- Quality bar -->
    <div class="flex items-center gap-3 mb-2">
      <div class="flex-1 h-1.5 bg-ocean-deep rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-500"
          :class="barColor"
          :style="{ width: barWidth }"
        />
      </div>
      <span class="text-[11px] font-semibold uppercase tracking-wider whitespace-nowrap" :class="labelColor">
        {{ label }}
      </span>
    </div>

    <!-- Inline tips -->
    <div v-if="activeTips.length" class="space-y-1">
      <div
        v-for="tip in activeTips"
        :key="tip"
        class="flex items-start gap-1.5 text-[12px] text-mist-slate leading-snug"
      >
        <span class="flex-shrink-0 mt-px text-ocean-cyan/60">›</span>
        <span>{{ tip }}</span>
      </div>
    </div>
    <div v-else-if="goal.trim()" class="text-[12px] text-organic-seafoam flex items-center gap-1.5">
      <span>✓</span>
      <span>Goal looks great — clear, specific, and well-framed.</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  goal: { type: String, default: '' },
})

const TIMEFRAME_RE = /\b(\d+\s*(day|week|month|quarter|year)s?|over\s+\w+|within\s+\w+|next\s+\w+)\b/i
const CAUSAL_RE = /\b(how\s+will|what\s+will|react|respond|impact|influence|affect|emerge|cascade)\b/i
const STAKEHOLDER_RE = /\b(investor|analyst|regulator|consumer|customer|user|player|competitor|coalition|government|media|public|retail|institutional|trader|executive|ceo|cfo|firm|company|brand|market)s?\b/i

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length
}

const score = computed(() => {
  const g = props.goal
  if (!g.trim()) return 0
  let s = 0
  if (wordCount(g) >= 25) s++
  if (g.includes('?')) s++
  if (STAKEHOLDER_RE.test(g)) s++
  if (TIMEFRAME_RE.test(g)) s++
  if (CAUSAL_RE.test(g)) s++
  return s
})

const barWidth = computed(() => {
  const pct = Math.max(4, Math.round((score.value / 5) * 100))
  return `${pct}%`
})

const barColor = computed(() => {
  if (score.value <= 1) return 'bg-coral/70'
  if (score.value <= 3) return 'bg-amber-400'
  return 'bg-organic-seafoam'
})

const labelColor = computed(() => {
  if (score.value <= 1) return 'text-coral/80'
  if (score.value <= 3) return 'text-amber-400'
  return 'text-organic-seafoam'
})

const label = computed(() => {
  if (!props.goal.trim()) return 'Not started'
  if (score.value <= 1) return 'Weak'
  if (score.value <= 3) return 'Fair'
  return 'Strong'
})

const activeTips = computed(() => {
  if (!props.goal.trim()) return []
  const g = props.goal
  const tips = []
  if (wordCount(g) < 25) tips.push('Tip: Add more detail — longer goals produce more targeted analysis.')
  if (!g.includes('?')) tips.push("Tip: Frame as a question — 'How will...' or 'What will...'")
  if (!STAKEHOLDER_RE.test(g)) tips.push("Tip: Mention specific stakeholders (e.g. 'retail investors, regulators, media')")
  if (!TIMEFRAME_RE.test(g)) tips.push("Tip: Add a timeframe (e.g. 'over 30 days' or 'within the next quarter')")
  if (!CAUSAL_RE.test(g)) tips.push("Tip: Use cause-effect language — 'How will X react to Y?' or 'What shifts will emerge?'")
  return tips
})
</script>
