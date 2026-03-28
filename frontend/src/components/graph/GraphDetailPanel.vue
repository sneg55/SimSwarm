<template>
  <transition name="slide">
    <div
      v-if="node"
      class="absolute top-0 right-0 h-full w-80 bg-ocean-deep border-l border-mist-depth shadow-[0_8px_32px_rgba(0,0,0,0.4)] overflow-y-auto z-30"
    >
      <div class="p-4">
        <!-- Header -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="w-3 h-3 rounded-full flex-shrink-0"
              :style="{ backgroundColor: nodeColor }"
            ></span>
            <h3 class="text-sm font-semibold text-mist-foam truncate">{{ node.name }}</h3>
          </div>
          <button
            @click="$emit('close')"
            class="p-1 text-mist-slate hover:text-mist-drift flex-shrink-0"
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
          <p class="text-xs text-mist-drift leading-relaxed">{{ node.summary }}</p>
        </div>

        <!-- Relationships -->
        <div v-if="relationships.length > 0">
          <h4 class="text-[10px] font-bold tracking-wider text-mist-slate uppercase mb-2">Relationships</h4>

          <!-- Outgoing -->
          <div v-if="outgoing.length > 0" class="mb-3">
            <p class="text-[10px] text-mist-slate mb-1">Outgoing</p>
            <button
              v-for="rel in outgoing"
              :key="rel.target_uuid || rel.targetName"
              @click="$emit('navigate-to', rel.target_uuid)"
              class="w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded hover:bg-ocean-teal/10 transition-colors group"
            >
              <span class="text-xs text-mist-slate group-hover:text-ocean-glow">&#8594;</span>
              <span class="text-xs text-mist truncate flex-1">{{ rel.targetName || rel.target_uuid }}</span>
              <span class="text-[10px] text-mist-slate">{{ rel.type }}</span>
            </button>
          </div>

          <!-- Incoming -->
          <div v-if="incoming.length > 0">
            <p class="text-[10px] text-mist-slate mb-1">Incoming</p>
            <button
              v-for="rel in incoming"
              :key="rel.source_uuid || rel.sourceName"
              @click="$emit('navigate-to', rel.source_uuid)"
              class="w-full flex items-center gap-1.5 px-2 py-1.5 text-left rounded hover:bg-ocean-teal/10 transition-colors group"
            >
              <span class="text-xs text-mist-slate group-hover:text-ocean-glow">&#8592;</span>
              <span class="text-xs text-mist truncate flex-1">{{ rel.sourceName || rel.source_uuid }}</span>
              <span class="text-[10px] text-mist-slate">{{ rel.type }}</span>
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
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
