<template>
  <div class="mt-4">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-2">Forecast timeline</div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="preset in presets"
        :key="preset.days"
        @click="toggle(preset.days)"
        class="px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all duration-200"
        :class="modelValue === preset.days
          ? 'border-ocean-cyan bg-ocean-cyan/10 text-ocean-cyan'
          : 'border-mist-depth bg-ocean-deep text-mist-drift hover:border-mist-slate hover:text-mist-foam'"
      >
        {{ preset.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue'])

const presets = [
  { label: '1 day', days: 1 },
  { label: '1 week', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 180 },
  { label: '1 year', days: 365 },
]

function toggle(days) {
  emit('update:modelValue', props.modelValue === days ? null : days)
}
</script>
