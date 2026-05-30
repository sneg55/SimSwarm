<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-xl p-6 mb-4 transition-transform duration-300 hover:translate-x-1"
    :style="{ borderLeftWidth: '3px', borderLeftColor: accentColor }">
    <div class="font-mono text-xs tracking-wide mb-1.5" :style="{ color: accentColor }">{{ label }}</div>
    <h4 class="text-base font-bold text-mist-foam mb-2">{{ title }}</h4>
    <p class="text-[15px] text-mist leading-relaxed">{{ description }}</p>
    <InfoTooltip v-if="metric" copyKey="findingCard.metric">
      <div class="inline-flex items-center gap-1.5 mt-3 font-mono text-sm px-2.5 py-1 rounded-md"
        :style="{ color: accentColor, background: accentColor + '14' }">
        <span class="w-1.5 h-1.5 rounded-full" :style="{ background: accentColor }" />
        {{ metric }}
      </div>
    </InfoTooltip>
  </div>
</template>

<script setup>
import InfoTooltip from '../InfoTooltip.vue'

defineProps({
  label: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  metric: { type: String, default: '' },
  accentColor: { type: String, default: '#22D3EE' },
})
</script>
