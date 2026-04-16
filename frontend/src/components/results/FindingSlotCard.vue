<template>
  <div class="relative bg-ocean-deep border border-mist-depth rounded-2xl p-6 pl-7 transition-all duration-250 hover:border-ocean-cyan hover:-translate-y-px">
    <div :class="['absolute left-0 top-5 bottom-5 w-[3px] rounded-r-md', accentClass]"></div>
    <div :class="['font-mono text-[9px] tracking-[0.1em] uppercase font-semibold', labelClass]">{{ slotLabel }}</div>
    <div class="text-sm font-semibold text-mist-foam mt-2 leading-snug">{{ title }}</div>
    <div class="text-[13px] text-mist-drift mt-2.5 leading-relaxed">{{ body }}</div>
    <div v-if="citation" class="font-mono text-[10px] text-mist-slate mt-2.5 pt-2.5 border-t border-mist-depth">
      {{ citation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  slot: { type: String, required: true },
  title: { type: String, required: true },
  body: { type: String, required: true },
  citation: { type: String, default: '' },
})

const _labels = {
  industry: 'Industry posture',
  regulator: 'Regulator posture',
  intermediary: 'Intermediary role',
  market: 'Market signal',
  turning_point: 'Turning point',
}

const slotLabel = computed(() => _labels[props.slot] || props.slot)

const accentClass = computed(() => ({
  industry: 'bg-coral-amber',
  regulator: 'bg-ocean-glow',
  intermediary: 'bg-organic-violet',
  market: 'bg-organic-seafoam',
  turning_point: 'bg-coral',
})[props.slot] || 'bg-ocean-glow')

const labelClass = computed(() => ({
  industry: 'text-coral-amber',
  regulator: 'text-ocean-glow',
  intermediary: 'text-organic-violet',
  market: 'text-organic-seafoam',
  turning_point: 'text-coral',
})[props.slot] || 'text-ocean-glow')
</script>
