<template>
  <div class="fixed top-[52px] left-0 right-0 z-40 px-6 py-2 flex items-center justify-between glass border-b border-mist-depth/50">
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
