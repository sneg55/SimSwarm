<template>
  <div class="bg-ocean-abyss border border-mist-depth rounded-xl p-4 transition-all duration-300 hover:border-ocean-teal hover:-translate-y-0.5">
    <div class="flex items-center gap-2 text-sm font-semibold text-mist-foam mb-1">
      <span class="w-2 h-2 rounded-full" :style="{ background: color, boxShadow: `0 0 8px ${color}66` }" />
      {{ name }}
    </div>
    <p class="text-sm text-mist-drift leading-snug">{{ description }}</p>
    <div class="font-mono text-[11px] text-mist-slate mt-2">
      <InfoTooltip copyKey="coalitionCard.agents">{{ agents }} agents</InfoTooltip>
      &middot;
      <InfoTooltip copyKey="coalitionCard.strength">Strength: {{ strength }}%</InfoTooltip>
    </div>
  </div>
</template>

<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({
  name: { type: String, required: true },
  description: { type: String, required: true },
  agents: { type: Number, required: true },
  strength: { type: Number, required: true },
  color: { type: String, default: '#22D3EE' },
})
</script>
