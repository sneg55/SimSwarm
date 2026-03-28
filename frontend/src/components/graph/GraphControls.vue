<template>
  <div class="flex items-center gap-1.5">
    <!-- Refresh -->
    <button
      @click="$emit('refresh')"
      class="p-1.5 bg-ocean-deep border border-mist-depth rounded-lg hover:bg-ocean-teal/10 transition-colors"
      title="Re-layout"
    >
      <svg class="w-4 h-4 text-mist-drift" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    </button>

    <!-- Fullscreen toggle -->
    <button
      @click="$emit('toggle-fullscreen')"
      class="p-1.5 bg-ocean-deep border border-mist-depth rounded-lg hover:bg-ocean-teal/10 transition-colors"
      :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
    >
      <svg v-if="!isFullscreen" class="w-4 h-4 text-mist-drift" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
      </svg>
      <svg v-else class="w-4 h-4 text-mist-drift" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
      </svg>
    </button>

    <!-- Edge Labels toggle -->
    <div
      class="flex items-center gap-1.5 px-2 py-1 bg-ocean-deep border border-mist-depth rounded-lg cursor-pointer select-none"
      @click="$emit('toggle-edge-labels')"
    >
      <span class="text-xs text-mist-slate">Labels</span>
      <div
        class="relative w-7 h-4 rounded-full transition-colors"
        :class="showEdgeLabels ? 'bg-ocean-cyan' : 'bg-mist-depth'"
      >
        <div
          class="absolute top-0.5 w-3 h-3 bg-ocean-deep rounded-full shadow transition-transform"
          :class="showEdgeLabels ? 'translate-x-3.5' : 'translate-x-0.5'"
        ></div>
      </div>
    </div>

    <!-- Layout selector -->
    <select
      :value="layoutName"
      @change="$emit('change-layout', $event.target.value)"
      class="text-xs bg-ocean-deep border border-mist-depth rounded-lg px-2 py-1.5 text-mist-drift focus:outline-none focus:ring-2 focus:ring-ocean-cyan"
    >
      <option value="cose-bilkent">Force-directed</option>
      <option value="circle">Circle</option>
      <option value="dagre">Hierarchical</option>
      <option value="grid">Grid</option>
    </select>

    <!-- Export dropdown -->
    <div class="relative" ref="exportDropdownRef">
      <button
        @click="exportOpen = !exportOpen"
        class="p-1.5 bg-ocean-deep border border-mist-depth rounded-lg hover:bg-ocean-teal/10 transition-colors"
        title="Export image"
      >
        <svg class="w-4 h-4 text-mist-drift" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      </button>
      <div
        v-if="exportOpen"
        class="absolute right-0 mt-1 w-24 bg-ocean-deep border border-mist-depth rounded-lg shadow-[0_8px_32px_rgba(0,0,0,0.4)] overflow-hidden z-10"
      >
        <button
          @click="handleExport('png')"
          class="w-full text-left px-3 py-1.5 text-xs text-mist hover:bg-ocean-teal/10"
        >Export as PNG</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps({
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'cose-bilkent' },
  isFullscreen: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh', 'toggle-fullscreen', 'toggle-edge-labels', 'change-layout', 'export'])

const exportOpen = ref(false)
const exportDropdownRef = ref(null)

function handleExport(format) {
  emit('export', format)
  exportOpen.value = false
}

function onClickOutside(evt) {
  if (exportDropdownRef.value && !exportDropdownRef.value.contains(evt.target)) {
    exportOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})
</script>
