<template>
  <div class="bg-white/90 backdrop-blur border border-gray-200 rounded-lg shadow-sm p-3 max-w-xs">
    <div class="flex items-center justify-between mb-2">
      <span class="text-[10px] font-bold tracking-wider text-red-600 uppercase">Entity Types</span>
      <div class="flex gap-1">
        <button
          @click="$emit('show-all')"
          class="text-[10px] text-indigo-600 hover:text-indigo-800 font-medium"
        >All</button>
        <span class="text-gray-300 text-[10px]">|</span>
        <button
          @click="$emit('hide-all')"
          class="text-[10px] text-indigo-600 hover:text-indigo-800 font-medium"
        >None</button>
      </div>
    </div>

    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="et in entityTypes"
        :key="et.name"
        @click="$emit('toggle-type', et.name)"
        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs transition-opacity cursor-pointer hover:bg-gray-100"
        :class="hiddenTypes.has(et.name) ? 'opacity-30' : 'opacity-100'"
      >
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: et.color }"
        ></span>
        <span class="text-gray-700">{{ et.name }}</span>
        <span class="text-gray-400">({{ et.count }})</span>
      </button>
    </div>

    <div v-if="filterBanner" class="mt-2 pt-2 border-t border-gray-100">
      <div class="flex items-center justify-between">
        <span class="text-xs text-gray-500">{{ filterBanner }}</span>
        <button
          @click="$emit('show-all-nodes')"
          class="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
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
