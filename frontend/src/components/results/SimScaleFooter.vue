<template>
  <div class="flex gap-6 px-6 py-5 bg-ocean-deep/40 border border-mist-depth rounded-2xl">
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.participants ?? 0 }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Participants</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.horizon_days ?? 0 }}d</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Horizon</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ scale.bloc_count ?? 0 }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Blocs</div>
    </div>
    <div class="flex flex-col gap-0.5">
      <div class="text-base font-bold text-mist-foam">{{ marketStressLabel }}</div>
      <div class="font-mono text-[9px] tracking-wider uppercase text-mist-slate">Market stress</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scale: { type: Object, required: true },
})

const marketStressLabel = computed(() => {
  if (props.scale.market_stress === 'present') return 'Present'
  if (props.scale.market_stress === 'none_observed') return 'None'
  return '—'
})
</script>
