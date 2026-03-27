<template>
  <div class="inline-flex bg-gray-100 rounded-lg p-0.5">
    <button
      v-for="mode in availableModes"
      :key="mode.value"
      @click="$emit('update:modelValue', mode.value)"
      class="px-4 py-1.5 text-sm font-medium rounded-md transition-colors"
      :class="modelValue === mode.value
        ? 'bg-white text-gray-900 shadow-sm'
        : 'text-gray-500 hover:text-gray-700'"
    >
      {{ mode.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: 'report' },
  compact: { type: Boolean, default: false },
})

defineEmits(['update:modelValue'])

const allModes = [
  { value: 'graph', label: 'Graph' },
  { value: 'dual', label: 'Dual Column' },
  { value: 'report', label: 'Report' },
]

const availableModes = computed(() => {
  if (props.compact) return allModes.filter((m) => m.value !== 'dual')
  return allModes
})
</script>
