<template>
  <div class="fixed top-[56px] left-0 right-0 z-50 glass-solid border-b border-mist-depth/50">
    <div class="max-w-6xl mx-auto px-4 md:px-8 py-2.5 flex items-center justify-between">
    <div class="flex items-center gap-2 text-sm text-mist-slate min-w-0 flex-1 mr-4">
      <router-link :to="backLink" class="hover:text-mist-drift transition-colors flex-shrink-0">&larr; {{ backLabel }}</router-link>
      <span class="flex-shrink-0">/</span>
      <span class="text-mist-drift truncate" :title="title">{{ title }}</span>
    </div>
    <div class="flex items-center gap-3 flex-shrink-0">
      <slot name="controls" />
      <ViewModeToggle v-if="showToggle" :modelValue="viewMode" :showData="showData" @update:modelValue="$emit('update:viewMode', $event)" />
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
  backLink: { type: String, default: '/dashboard' },
  backLabel: { type: String, default: 'Dashboard' },
  showData: { type: Boolean, default: false },
})

defineEmits(['update:viewMode'])
</script>
