<template>
  <div class="fixed bottom-0 left-0 right-0 z-40 px-6 py-3 flex items-center justify-center gap-2 glass border-t border-mist-depth/50">
    <button
      v-if="showPng"
      @click="$emit('export', 'png')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      Export as PNG
    </button>
    <button
      @click="$emit('export', 'pdf')"
      :disabled="pdfLoading"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)] disabled:opacity-50"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      {{ pdfLoading ? 'Generating...' : 'Export as PDF' }}
    </button>
    <button
      v-if="showCsv"
      @click="$emit('export', 'csv')"
      class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-mist-drift bg-ocean-deep border border-mist-depth transition-all duration-250 ease-spring hover:border-ocean-teal hover:text-mist-foam hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v12"/><path d="m8 11 4 4 4-4"/><path d="M8 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-4"/></svg>
      Export as CSV
    </button>
    <button
      @click="$emit('share')"
      :disabled="shareStatus === 'generating'"
      :class="shareButtonClass"
    >
      <svg v-if="shareStatus !== 'copied'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
      {{ shareLabel }}
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  showPng: { type: Boolean, default: false },
  showCsv: { type: Boolean, default: true },
  pdfLoading: { type: Boolean, default: false },
  shareStatus: { type: String, default: '' },
})

defineEmits(['export', 'share'])

const shareLabel = computed(() => {
  if (props.shareStatus === 'generating') return 'Generating link...'
  if (props.shareStatus === 'copied') return 'Link copied!'
  if (props.shareStatus === 'error') return 'Failed — try again'
  return 'Share simulation'
})

const shareButtonClass = computed(() => {
  const base = 'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-250 ease-spring'
  if (props.shareStatus === 'copied') {
    return `${base} text-white bg-emerald-600 shadow-[0_0_16px_rgba(16,185,129,0.4)]`
  }
  if (props.shareStatus === 'error') {
    return `${base} text-white bg-coral/80`
  }
  return `${base} text-white bg-gradient-to-br from-ocean-cyan to-cyan-500 glow-cyan hover:glow-cyan-lg hover:-translate-y-0.5 disabled:opacity-50`
})
</script>
