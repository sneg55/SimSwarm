<template>
  <div class="fixed top-[56px] left-0 right-0 z-40 glass-solid border-b border-mist-depth/50">
    <div class="max-w-6xl mx-auto px-4 md:px-8 py-2.5 flex items-center justify-between">
    <div class="flex items-center gap-2 text-sm text-mist-slate">
      <router-link to="/dashboard" class="hover:text-mist-drift transition-colors">&larr; Dashboard</router-link>
      <span>/</span>
      <span class="text-mist-drift">{{ title }}</span>
    </div>
    <div class="flex items-center gap-3">
      <slot name="controls" />
      <ViewModeToggle v-if="showToggle" :modelValue="viewMode" @update:modelValue="$emit('update:viewMode', $event)" />
    </div>
    </div>
  </div>
</template>

<script setup>
import ViewModeToggle from '../ViewModeToggle.vue'

defineProps({
  title: { type: String, default: 'Results' },
  viewMode: { type: String, default: 'story' },
  showToggle: { type: Boolean, default: true },
})

defineEmits(['update:viewMode'])
</script>
