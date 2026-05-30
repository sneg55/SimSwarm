<template>
  <div class="relative bg-ocean-deep border border-mist-depth rounded-2xl p-6 pl-7 transition-all duration-250 hover:border-ocean-cyan hover:-translate-y-px">
    <div :class="['absolute left-0 top-5 bottom-5 w-[3px] rounded-r-md', accentClass]"></div>
    <div :class="['font-mono text-[11px] tracking-[0.1em] uppercase font-semibold', labelClass]">{{ slotLabel }}</div>
    <div class="text-lg font-semibold text-mist-foam mt-2 leading-snug">{{ title }}</div>
    <div class="text-[15px] text-mist-drift mt-3 leading-relaxed">{{ body }}</div>
    <div v-if="citation" class="font-mono text-[12px] text-mist-drift mt-3 pt-3 border-t border-mist-depth leading-relaxed">
      {{ citation }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// `slotName` (not `slot`) — `slot` is a reserved attribute name in Vue and
// passing `:slot="..."` from a parent template gets stripped by the compiler.
const props = defineProps({
  slotName: { type: String, required: true },
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

const slotLabel = computed(() => _labels[props.slotName] || props.slotName)

const accentClass = computed(() => ({
  industry: 'bg-coral-amber',
  regulator: 'bg-ocean-glow',
  intermediary: 'bg-organic-violet',
  market: 'bg-organic-seafoam',
  turning_point: 'bg-coral',
})[props.slotName] || 'bg-ocean-glow')

const labelClass = computed(() => ({
  industry: 'text-coral-amber',
  regulator: 'text-ocean-glow',
  intermediary: 'text-organic-violet',
  market: 'text-organic-seafoam',
  turning_point: 'text-coral',
})[props.slotName] || 'text-ocean-glow')
</script>
