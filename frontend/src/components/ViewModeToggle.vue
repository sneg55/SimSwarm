<template>
  <div class="inline-flex gap-0.5 bg-ocean-deep border border-mist-depth rounded-xl p-0.5">
    <button
      v-for="mode in availableModes"
      :key="mode.value"
      @click="$emit('update:modelValue', mode.value)"
      class="px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all duration-250"
      :class="modelValue === mode.value
        ? 'bg-ocean-cyan/20 text-mist-foam'
        : 'text-mist-slate hover:text-mist-drift'"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: 'story' },
  compact: { type: Boolean, default: false },
  showData: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const baseModes = [
  { value: 'story', label: 'Story' },
  { value: 'graph', label: 'Graph' },
  { value: 'report', label: 'Report' },
]

const availableModes = computed(() => {
  const modes = [...baseModes]
  if (props.showData) {
    modes.splice(2, 0, { value: 'data', label: 'Data' })
  }
  if (props.compact) return modes.filter((m) => m.value !== 'dual')
  return modes
})
</script>
