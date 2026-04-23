<template>
  <div v-if="start && end && roundCount >= 1"
       data-timeline-band
       class="relative w-full py-6 px-4 bg-ocean-deep border-y border-mist-depth">
    <!-- Date axis -->
    <div class="relative h-4 mb-2">
      <span v-for="tick in ticks" :key="tick.label"
            :style="{ left: tick.pct + '%' }"
            class="absolute text-[10px] font-mono uppercase tracking-wider text-mist-slate -translate-x-1/2">
        {{ tick.label }}
      </span>
    </div>

    <!-- Baseline + dots -->
    <div class="relative h-[56px]">
      <div class="absolute left-0 right-0 top-1/2 h-px bg-mist-depth"></div>

      <template v-for="cluster in clusters" :key="cluster.position">
        <button
          v-if="cluster.items.length > 1"
          data-timeline-cluster
          :style="{ left: (cluster.position * 100) + '%' }"
          :class="['absolute top-1/2 -translate-x-1/2 -translate-y-1/2 px-2 py-0.5 rounded-full text-[10px] font-medium border transition-colors', clusterTint(cluster.items)]"
          @click="$emit('clusterClick', cluster)"
        >+{{ cluster.items.length }}</button>

        <button
          v-else
          data-timeline-dot
          :style="{ left: (cluster.position * 100) + '%' }"
          :class="['absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-transform hover:scale-150',
                    typeColor(cluster.items[0].type)]"
          :title="cluster.items[0].title"
          @click="$emit('select', cluster.items[0].id)"
        />
      </template>

      <div v-if="roundCount > 1"
           class="absolute top-full mt-1 h-0.5 bg-ocean-teal transition-all duration-200"
           :style="{ left: 0, width: progressPct + '%' }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { clusterMoments } from '@/composables/useSimTimeline'
import { useStoryScrollSync } from '@/composables/useStoryScrollSync'

const props = defineProps({
  start: { type: Date, default: null },
  end: { type: Date, default: null },
  roundCount: { type: Number, default: 0 },
  moments: { type: Array, default: () => [] },
})
defineEmits(['select', 'clusterClick'])

const { activeRoundIndex } = useStoryScrollSync()

const clusters = computed(() => clusterMoments(props.moments, props.roundCount, 0.02))

const progressPct = computed(() => {
  if (props.roundCount <= 1) return 0
  return (activeRoundIndex.value / (props.roundCount - 1)) * 100
})

const ticks = computed(() => {
  if (!props.start || !props.end) return []
  const span = props.end - props.start
  const fmt = pickFormatter(span)
  return [0, 0.25, 0.5, 0.75, 1].map(pct => ({
    pct: pct * 100,
    label: fmt(new Date(props.start.getTime() + span * pct)),
  }))
})

function pickFormatter(spanMs) {
  const days = spanMs / (86400 * 1000)
  if (days <= 2) return d => d.toISOString().slice(11, 16) + 'Z'
  if (days <= 60) return d => d.toLocaleString('en-US', { month: 'short', day: 'numeric' })
  if (days <= 365) return d => d.toLocaleString('en-US', { month: 'short', day: 'numeric' })
  return d => d.toLocaleString('en-US', { month: 'short', year: '2-digit' })
}

function dominantType(items) {
  const counts = {}
  for (const it of items) counts[it.type] = (counts[it.type] || 0) + 1
  let best = null, bestCount = 0
  for (const [t, c] of Object.entries(counts)) {
    if (c > bestCount) { best = t; bestCount = c }
  }
  return best
}

function clusterTint(items) {
  const t = dominantType(items)
  switch (t) {
    case 'market':    return 'border-coral/60 bg-coral/10 text-coral'
    case 'coalition': return 'border-ocean-teal/60 bg-ocean-teal/10 text-ocean-teal'
    case 'post':      return 'border-ocean-glow/60 bg-ocean-glow/10 text-ocean-glow'
    case 'finding':   return 'border-amber-400/60 bg-amber-400/10 text-amber-400'
    default:          return 'border-mist-slate bg-mist-depth text-mist-foam'
  }
}

function typeColor(type) {
  switch (type) {
    case 'market':    return 'bg-coral shadow-[0_0_8px_rgba(251,113,133,0.5)]'
    case 'coalition': return 'bg-ocean-teal shadow-[0_0_8px_rgba(34,211,238,0.4)]'
    case 'post':      return 'bg-ocean-glow shadow-[0_0_8px_rgba(34,211,238,0.6)]'
    case 'finding':   return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'
    default:          return 'bg-mist-slate'
  }
}
</script>
