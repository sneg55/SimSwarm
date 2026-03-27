<template>
  <transition name="slide">
    <div
      v-if="node"
      class="absolute top-0 right-0 h-full w-80 bg-white border-l border-gray-200 shadow-lg overflow-y-auto z-30"
    >
      <div class="p-4">
        <!-- Header -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="w-3 h-3 rounded-full flex-shrink-0"
              :style="{ backgroundColor: nodeColor }"
            ></span>
            <h3 class="text-sm font-semibold text-gray-900 truncate">{{ node.name }}</h3>
          </div>
          <button
            @click="$emit('close')"
            class="p-1 text-gray-400 hover:text-gray-600 flex-shrink-0"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Type badge -->
        <span
          class="inline-block text-xs font-medium px-2 py-0.5 rounded-full mb-3"
          :style="{ backgroundColor: nodeColor + '20', color: nodeColor }"
        >{{ node.entityType }}</span>

        <!-- Summary -->
        <div v-if="node.summary" class="mb-4">
          <p class="text-xs text-gray-600 leading-relaxed">{{ node.summary }}</p>
        </div>

        <!-- Relationships -->
        <div v-if="relationships.length > 0">
          <h4 class="text-[10px] font-bold tracking-wider text-gray-500 uppercase mb-2">Relationships</h4>

          <!-- Outgoing -->
          <div v-if="outgoing.length > 0" class="mb-3">
            <p class="text-[10px] text-gray-400 mb-1">Outgoing</p>
            <button
              v-for="rel in outgoing"
              :key="rel.target_uuid || rel.targetName"
              @click="$emit('navigate-to', rel.target_uuid)"
              class="w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded hover:bg-gray-50 transition-colors group"
            >
              <span class="text-xs text-gray-400 group-hover:text-indigo-500">&#8594;</span>
              <span class="text-xs text-gray-700 truncate flex-1">{{ rel.targetName || rel.target_uuid }}</span>
              <span class="text-[10px] text-gray-400">{{ rel.type }}</span>
            </button>
          </div>

          <!-- Incoming -->
          <div v-if="incoming.length > 0">
            <p class="text-[10px] text-gray-400 mb-1">Incoming</p>
            <button
              v-for="rel in incoming"
              :key="rel.source_uuid || rel.sourceName"
              @click="$emit('navigate-to', rel.source_uuid)"
              class="w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded hover:bg-gray-50 transition-colors group"
            >
              <span class="text-xs text-gray-400 group-hover:text-indigo-500">&#8592;</span>
              <span class="text-xs text-gray-700 truncate flex-1">{{ rel.sourceName || rel.source_uuid }}</span>
              <span class="text-[10px] text-gray-400">{{ rel.type }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { getEntityColor } from './graphColors.js'

const props = defineProps({
  node: { type: Object, default: null },
})

defineEmits(['close', 'navigate-to'])

const nodeColor = computed(() => {
  if (!props.node) return '#6b7280'
  return getEntityColor(props.node.entityType || 'Entity')
})

const relationships = computed(() => {
  if (!props.node || !props.node.relationships) return []
  return props.node.relationships
})

const outgoing = computed(() =>
  relationships.value.filter((r) => r.direction === 'outgoing' || r.source_uuid === props.node?.id)
)

const incoming = computed(() =>
  relationships.value.filter((r) => r.direction === 'incoming' || r.target_uuid === props.node?.id)
)
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
