<template>
  <div class="bg-ocean-deep/90 backdrop-blur border border-mist-depth rounded-lg p-3 w-48">
    <!-- Entity Types -->
    <div class="flex items-center justify-between mb-2">
      <span class="text-[10px] font-bold tracking-wider text-ocean-cyan uppercase">Entity Types</span>
      <div class="flex gap-1">
        <button @click="$emit('show-all')" class="text-[10px] text-ocean-cyan hover:text-ocean-glow font-medium">All</button>
        <button @click="$emit('hide-all')" class="text-[10px] text-ocean-cyan hover:text-ocean-glow font-medium">None</button>
      </div>
    </div>

    <div class="space-y-0.5">
      <button
        v-for="et in entityTypes"
        :key="et.name"
        @click="$emit('toggle-type', et.name)"
        class="w-full flex items-center gap-2 py-1 px-1 rounded text-xs transition-opacity cursor-pointer hover:bg-ocean-teal/10"
        :class="hiddenTypes.has(et.name) ? 'opacity-30' : 'opacity-100'"
      >
        <span class="w-2.5 h-2.5 rounded-full flex-shrink-0" :style="{ backgroundColor: et.color }" />
        <span class="text-mist flex-1 text-left">{{ et.name }}</span>
        <span class="text-mist-slate font-mono text-[10px]">{{ et.count }}</span>
      </button>
    </div>

    <!-- Sentiment -->
    <div class="mt-3 pt-3 border-t border-mist-depth">
      <div class="text-[10px] font-bold tracking-wider text-mist-slate uppercase mb-2">Sentiment</div>
      <div class="space-y-0.5">
        <div class="flex items-center gap-2 py-1 px-1 text-xs">
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0 border-2 border-[#6EE7B7] bg-transparent" />
          <span class="text-[#6EE7B7] flex-1">Positive</span>
          <span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.positive }}</span>
        </div>
        <div class="flex items-center gap-2 py-1 px-1 text-xs">
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0 border-2 border-[#FF6B6B] bg-transparent" />
          <span class="text-[#FF6B6B] flex-1">Negative</span>
          <span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.negative }}</span>
        </div>
        <div class="flex items-center gap-2 py-1 px-1 text-xs">
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0 border-2 border-[#94A3B8] bg-transparent" />
          <span class="text-[#94A3B8] flex-1">Neutral</span>
          <span class="text-mist-slate font-mono text-[10px]">{{ sentimentCounts.neutral }}</span>
        </div>
      </div>
    </div>

    <!-- Filter banner -->
    <div v-if="filterBanner" class="mt-2 pt-2 border-t border-mist-depth">
      <div class="flex items-center justify-between">
        <span class="text-xs text-mist-slate">{{ filterBanner }}</span>
        <button @click="$emit('show-all-nodes')" class="text-xs text-ocean-cyan hover:text-ocean-glow font-medium">Show all</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  entityTypes: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  filterBanner: { type: String, default: '' },
  nodes: { type: Array, default: () => [] },
})

defineEmits(['toggle-type', 'show-all', 'hide-all', 'show-all-nodes'])

const sentimentCounts = computed(() => {
  let positive = 0, negative = 0, neutral = 0
  for (const n of props.nodes) {
    const s = n.sentiment ?? 0
    if (s > 0.2) positive++
    else if (s < -0.2) negative++
    else neutral++
  }
  return { positive, negative, neutral }
})
</script>
