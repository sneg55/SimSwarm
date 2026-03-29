<template>
  <div class="bg-ocean-deep/90 backdrop-blur border border-mist-depth rounded-lg p-3 max-w-xs">
    <div class="flex items-center justify-between mb-2">
      <span class="text-[10px] font-bold tracking-wider text-ocean-cyan uppercase">Entity Types</span>
      <div class="flex gap-1">
        <button
          @click="$emit('show-all')"
          class="text-[10px] text-ocean-cyan hover:text-ocean-glow font-medium"
        >All</button>
        <span class="text-mist-depth text-[10px]">|</span>
        <button
          @click="$emit('hide-all')"
          class="text-[10px] text-ocean-cyan hover:text-ocean-glow font-medium"
        >None</button>
      </div>
    </div>

    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="et in entityTypes"
        :key="et.name"
        @click="$emit('toggle-type', et.name)"
        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs transition-opacity cursor-pointer hover:bg-ocean-teal/10"
        :class="hiddenTypes.has(et.name) ? 'opacity-30' : 'opacity-100'"
      >
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: et.color }"
        ></span>
        <span class="text-mist">{{ et.name }}</span>
        <span class="text-mist-slate">({{ et.count }})</span>
      </button>
    </div>

    <!-- Sentiment section -->
    <div class="mt-3 pt-3 border-t border-mist-depth">
      <div class="text-[10px] font-bold tracking-wider text-mist-slate uppercase mb-2">Sentiment</div>
      <div class="flex flex-wrap gap-1.5">
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs">
          <span class="w-2 h-2 rounded-full" style="background: #6EE7B7;"></span>
          <span class="text-[#6EE7B7]">Positive</span>
        </span>
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs">
          <span class="w-2 h-2 rounded-full" style="background: #FF6B6B;"></span>
          <span class="text-[#FF6B6B]">Negative</span>
        </span>
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs">
          <span class="w-2 h-2 rounded-full" style="background: #94A3B8;"></span>
          <span class="text-[#94A3B8]">Neutral</span>
        </span>
      </div>
    </div>

    <div v-if="filterBanner" class="mt-2 pt-2 border-t border-mist-depth">
      <div class="flex items-center justify-between">
        <span class="text-xs text-mist-slate">{{ filterBanner }}</span>
        <button
          @click="$emit('show-all-nodes')"
          class="text-xs text-ocean-cyan hover:text-ocean-glow font-medium"
        >Show all</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  entityTypes: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  filterBanner: { type: String, default: '' },
})

defineEmits(['toggle-type', 'show-all', 'hide-all', 'show-all-nodes'])
</script>
