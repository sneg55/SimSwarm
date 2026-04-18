<template>
  <span :class="['inline-flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-full border font-medium', styleFor(stance)]">
    <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
    {{ name }} · {{ detail }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  stance: { type: String, required: true }, // opposed | supports | neutral | split
  memberCount: { type: Number, default: 0 },
  rationaleKeywords: { type: Array, default: () => [] },
})

const stanceLabel = computed(() => {
  const labels = { opposed: 'Opposed', supports: 'Supports', neutral: 'Neutral', split: 'Split' }
  return labels[props.stance] || props.stance
})

const detail = computed(() => {
  if (!props.memberCount) return stanceLabel.value
  const count = `${props.memberCount} ${props.memberCount === 1 ? 'agent' : 'agents'}`
  const kw = (props.rationaleKeywords || []).slice(0, 3).join(', ')
  return kw ? `${count} · ${kw}` : count
})

function styleFor(stance) {
  const map = {
    opposed:  'border-coral-amber/40 text-coral-amber bg-coral-amber/10',
    supports: 'border-ocean-glow/40 text-ocean-glow bg-ocean-glow/10',
    split:    'border-organic-violet/40 text-organic-violet bg-organic-violet/10',
    neutral:  'border-mist-depth text-mist bg-ocean-deep/60',
  }
  return map[stance] || map.neutral
}
</script>
