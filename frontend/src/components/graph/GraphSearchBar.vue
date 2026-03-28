<template>
  <div ref="wrapperRef" class="relative w-64">
    <div class="flex items-center bg-ocean-deep border border-mist-depth rounded-lg px-2.5 py-1.5">
      <svg class="w-4 h-4 text-mist-slate mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        ref="inputRef"
        v-model="query"
        @input="onInput"
        @keydown.enter.prevent="selectFirst"
        @keydown.escape="close"
        @focus="open = true"
        type="text"
        placeholder="Search entities..."
        class="w-full text-sm text-mist placeholder-mist-slate/50 bg-transparent outline-none"
      />
    </div>

    <div
      v-if="open && filteredNodes.length > 0"
      class="absolute top-full left-0 right-0 mt-1 bg-ocean-deep border border-mist-depth rounded-lg shadow-[0_8px_32px_rgba(0,0,0,0.4)] max-h-60 overflow-y-auto z-20"
    >
      <button
        v-for="node in filteredNodes"
        :key="node.uuid"
        @click="selectNode(node)"
        class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-ocean-teal/10 transition-colors"
      >
        <span
          class="w-2.5 h-2.5 rounded-full flex-shrink-0"
          :style="{ backgroundColor: node._color }"
        ></span>
        <span class="text-sm text-mist-foam truncate flex-1">{{ node.name }}</span>
        <span class="text-xs text-mist-slate bg-ocean-abyss px-1.5 py-0.5 rounded">{{ node._entityType }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
})

const emit = defineEmits(['select-node'])

const query = ref('')
const open = ref(false)
const inputRef = ref(null)

const enrichedNodes = computed(() =>
  props.nodes.map((n) => {
    const entityType = getPrimaryLabel(n.labels || ['Entity'])
    return {
      ...n,
      _entityType: entityType,
      _color: getEntityColor(entityType),
    }
  })
)

const filteredNodes = computed(() => {
  if (!query.value.trim()) return []
  const q = query.value.toLowerCase()
  return enrichedNodes.value
    .filter((n) =>
      (n.name || '').toLowerCase().includes(q) ||
      n._entityType.toLowerCase().includes(q)
    )
    .slice(0, 20)
})

function onInput() {
  open.value = true
}

function selectNode(node) {
  emit('select-node', node.uuid)
  query.value = node.name || ''
  open.value = false
}

function selectFirst() {
  if (filteredNodes.value.length > 0) {
    selectNode(filteredNodes.value[0])
  }
}

function close() {
  open.value = false
  query.value = ''
}

const wrapperRef = ref(null)
function handleClickOutside(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}
onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))
</script>
