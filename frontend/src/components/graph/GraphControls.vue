<template>
  <div class="flex items-center gap-1.5">
    <!-- Zoom to fit -->
    <button
      @click="$emit('zoom-fit')"
      class="ctrl-btn"
      title="Zoom to fit"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        <line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
      </svg>
    </button>

    <!-- Reset layout -->
    <button
      @click="$emit('refresh')"
      class="ctrl-btn"
      title="Reset layout"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
      </svg>
    </button>

    <div class="w-px h-5 bg-mist-depth" />

    <!-- Group by toggle (Type / Sentiment) -->
    <div class="flex gap-0.5 bg-ocean-deep border border-mist-depth rounded-lg p-0.5">
      <button
        class="text-xs font-medium px-3 py-1 rounded-md transition-all"
        :class="groupBy === 'type' ? 'text-mist-foam bg-ocean-teal/20' : 'text-mist-slate hover:text-mist-drift'"
        @click="$emit('set-group-by', 'type')"
      >Type</button>
      <button
        class="text-xs font-medium px-3 py-1 rounded-md transition-all"
        :class="groupBy === 'sentiment' ? 'text-mist-foam bg-ocean-teal/20' : 'text-mist-slate hover:text-mist-drift'"
        @click="$emit('set-group-by', 'sentiment')"
      >Sentiment</button>
    </div>

    <div class="w-px h-5 bg-mist-depth" />

    <!-- Edge Labels toggle -->
    <button
      @click="$emit('toggle-edge-labels')"
      class="ctrl-btn"
      :class="showEdgeLabels ? 'text-ocean-cyan border-ocean-teal' : ''"
      title="Toggle edge labels"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
      </svg>
    </button>

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

    <div class="w-px h-5 bg-mist-depth" />

    <!-- Export PNG -->
    <button
      @click="$emit('export')"
      class="ctrl-btn"
      title="Export PNG"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
    </button>

    <!-- Fullscreen toggle -->
    <button
      @click="$emit('toggle-fullscreen')"
      class="ctrl-btn"
      :title="isFullscreen ? 'Exit fullscreen' : 'Fullscreen'"
    >
      <svg v-if="!isFullscreen" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
        <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
      </svg>
      <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" stroke-linecap="round">
        <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
        <line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
// no imports needed — all events delegated to parent

defineProps({
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'cose-bilkent' },
  isFullscreen: { type: Boolean, default: false },
  groupBy: { type: String, default: 'type' },
})

defineEmits(['refresh', 'zoom-fit', 'toggle-fullscreen', 'toggle-edge-labels', 'change-layout', 'set-group-by', 'export'])
</script>

<style scoped>
.ctrl-btn {
  @apply p-1.5 bg-ocean-deep border border-mist-depth rounded-lg text-mist-drift transition-all;
}
.ctrl-btn:hover {
  @apply bg-ocean-teal/10 text-mist-foam border-ocean-teal/30;
}
</style>
