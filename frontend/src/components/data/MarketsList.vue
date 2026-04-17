<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl p-5">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-3">
      Prediction Markets
    </div>
    <div v-if="rows.length" class="space-y-2">
      <div v-for="(m, idx) in rows" :key="idx"
           data-test="market-row"
           class="flex flex-col gap-1 p-3 rounded-lg bg-ocean-abyss/40 border border-mist-depth/60">
        <div class="flex items-baseline justify-between gap-3">
          <span class="text-sm text-ocean-cyan truncate">{{ m.question }}</span>
          <span class="text-xs font-mono text-mist-slate">
            YES {{ Math.round((m.initial_price_yes ?? 0.5) * 100) }}%
          </span>
        </div>
        <div v-if="m.rationale" data-test="market-rationale"
             class="text-xs text-mist-drift leading-relaxed">
          {{ m.rationale }}
        </div>
      </div>
    </div>
    <div v-else class="text-xs text-mist-slate text-center py-6">
      No markets for this simulation.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  markets: { type: Array, default: () => [] },
})

const rows = computed(() => Array.isArray(props.markets) ? props.markets : [])
</script>
