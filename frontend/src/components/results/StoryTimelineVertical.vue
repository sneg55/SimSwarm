<template>
  <div v-if="items.length" class="relative py-12">
    <div class="font-mono text-[10px] text-mist-slate uppercase tracking-wider mb-6 pl-1">
      Simulation timeline
    </div>
    <div class="relative">
      <!-- Central spine -->
      <div class="absolute left-1/2 top-0 bottom-0 w-px bg-mist-depth -translate-x-1/2"></div>

      <div class="flex flex-col gap-8">
        <div
          v-for="(m, i) in items"
          :key="m.id"
          data-timeline-row
          class="relative grid grid-cols-[1fr_auto_1fr] items-center gap-4"
        >
          <!-- Left card (odd index = 0, 2, 4…) -->
          <div v-if="i % 2 === 0" class="pr-2 flex justify-end">
            <div
              data-card-side="left"
              class="max-w-[360px] w-full bg-ocean-deep border border-mist-depth rounded-2xl p-4 hover:border-ocean-glow/60 transition-colors"
            >
              <div class="flex items-center gap-2 mb-2">
                <span
                  :class="['text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border', typeBadge(m.type)]"
                >
                  {{ typeLabel(m.type) }}
                </span>
                <span class="text-[11px] text-mist-slate font-mono">Round {{ (m.roundIndex ?? 0) + 1 }}</span>
              </div>
              <div class="text-[15px] font-semibold text-mist-foam mb-1 leading-6">{{ m.title }}</div>
              <div v-if="m.detail" class="text-[13px] text-mist-drift leading-[22px]">{{ m.detail }}</div>
            </div>
          </div>
          <div v-else></div>

          <!-- Spine: circle + date -->
          <div class="flex flex-col items-center relative z-10">
            <div
              :class="[
                'w-8 h-8 rounded-full border-2 border-ocean-midnight flex items-center justify-center',
                circleBg(m.type),
              ]"
            >
              <div class="w-2 h-2 rounded-full bg-ocean-midnight"></div>
            </div>
            <div class="text-[11px] font-mono uppercase tracking-wider text-mist-slate mt-1 whitespace-nowrap">
              {{ formatDate(m.date) }}
            </div>
          </div>

          <!-- Right card (even) -->
          <div v-if="i % 2 === 1" class="pl-2 flex justify-start">
            <div
              data-card-side="right"
              class="max-w-[360px] w-full bg-ocean-deep border border-mist-depth rounded-2xl p-4 hover:border-ocean-glow/60 transition-colors"
            >
              <div class="flex items-center gap-2 mb-2">
                <span
                  :class="['text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border', typeBadge(m.type)]"
                >
                  {{ typeLabel(m.type) }}
                </span>
                <span class="text-[11px] text-mist-slate font-mono">Round {{ (m.roundIndex ?? 0) + 1 }}</span>
              </div>
              <div class="text-[15px] font-semibold text-mist-foam mb-1 leading-6">{{ m.title }}</div>
              <div v-if="m.detail" class="text-[13px] text-mist-drift leading-[22px]">{{ m.detail }}</div>
            </div>
          </div>
          <div v-else></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  moments: { type: Array, default: () => [] },
  start: { type: [Date, null], default: null },
  end: { type: [Date, null], default: null },
  roundCount: { type: Number, default: 0 },
})

const items = computed(() =>
  [...(props.moments || [])].sort((a, b) => (a.roundIndex ?? 0) - (b.roundIndex ?? 0))
)

function circleBg(type) {
  switch (type) {
    case 'market':    return 'bg-coral'
    case 'coalition': return 'bg-ocean-teal'
    case 'post':      return 'bg-ocean-glow'
    case 'finding':   return 'bg-amber-400'
    default:          return 'bg-mist-slate'
  }
}

function typeBadge(type) {
  switch (type) {
    case 'market':    return 'border-coral/40 text-coral bg-coral/10'
    case 'coalition': return 'border-ocean-teal/40 text-ocean-teal bg-ocean-teal/10'
    case 'post':      return 'border-ocean-glow/40 text-ocean-glow bg-ocean-glow/10'
    case 'finding':   return 'border-amber-400/40 text-amber-400 bg-amber-400/10'
    default:          return 'border-mist-slate text-mist-slate bg-mist-depth'
  }
}

function typeLabel(type) {
  return ({ market: 'Market', coalition: 'Coalition', post: 'Viral post', finding: 'Finding' })[type] || type
}

function formatDate(d) {
  if (!d) return ''
  try {
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}
</script>
