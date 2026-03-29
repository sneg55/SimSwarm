<template>
  <div
    ref="wrapperRef"
    class="relative bg-ocean-abyss rounded-xl border border-mist-depth overflow-hidden"
    :class="isFullscreen ? 'fixed inset-0 z-50 rounded-none' : 'h-full'"
  >
    <!-- Loading state -->
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-ocean-abyss/80 z-40">
      <div class="flex flex-col items-center gap-2">
        <svg class="animate-spin h-8 w-8 text-ocean-glow" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span class="text-sm text-mist-slate">Loading graph...</span>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="absolute inset-0 flex items-center justify-center">
      <div class="text-center">
        <p class="text-sm text-ocean-cyan mb-2">{{ error }}</p>
      </div>
    </div>

    <!-- Graph content -->
    <template v-else>
      <!-- Ambient particles -->
      <div class="ambient-particles" aria-hidden="true">
        <div v-for="i in 30" :key="i" class="particle"
          :style="{
            left: `${(i * 37 + 13) % 100}%`,
            top: `${(i * 53 + 7) % 100}%`,
            width: `${2 + (i % 3)}px`,
            height: `${2 + (i % 3)}px`,
            opacity: 0.15 + (i % 5) * 0.05,
            animationDelay: `${(i * 0.7) % 8}s`,
            animationDuration: `${6 + (i % 4) * 2}s`,
          }"
        />
      </div>

      <GraphCanvas
        ref="canvasRef"
        :nodes="visibleNodes"
        :edges="edges"
        :hidden-types="hiddenTypes"
        :show-edge-labels="showEdgeLabels"
        :layout-name="layoutName"
        :selected-node-id="selectedNode?.id || null"
        @node-click="onNodeClick"
        @node-hover="onNodeHover"
        @node-unhover="onNodeUnhover"
        @ready="onCanvasReady"
      />

      <!-- Search bar (top-left) -->
      <div class="absolute top-3 left-3 z-10">
        <GraphSearchBar
          :nodes="allNodes"
          @select-node="onSearchSelect"
        />
      </div>

      <!-- Controls (top-right) -->
      <div class="absolute top-3 right-3 z-10">
        <GraphControls
          :show-edge-labels="showEdgeLabels"
          :layout-name="layoutName"
          :is-fullscreen="isFullscreen"
          :group-by="groupBy"
          @refresh="onRefresh"
          @zoom-fit="onZoomFit"
          @toggle-fullscreen="toggleFullscreen"
          @toggle-edge-labels="showEdgeLabels = !showEdgeLabels"
          @change-layout="layoutName = $event"
          @set-group-by="groupBy = $event"
          @export="onExport"
        />
      </div>

      <!-- Legend (bottom-left) -->
      <div class="absolute bottom-3 left-3 z-10">
        <GraphLegend
          :entity-types="entityTypeSummary"
          :hidden-types="hiddenTypes"
          :filter-banner="filterBanner"
          @toggle-type="toggleType"
          @show-all="showAllTypes"
          @hide-all="hideAllTypes"
          @show-all-nodes="showAllNodes"
        />
      </div>

      <!-- Detail panel (right side) -->
      <GraphDetailPanel
        :node="selectedNode"
        @close="selectedNode = null"
        @navigate-to="navigateToNode"
      />

      <!-- Hover tooltip -->
      <div
        v-if="hoveredNode"
        class="absolute pointer-events-none z-20 bg-ocean-deep/95 backdrop-blur text-mist-foam text-xs rounded-lg px-3 py-2 border border-ocean-teal/30 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
        :style="{ left: hoveredNode.x + 12 + 'px', top: hoveredNode.y - 8 + 'px' }"
      >
        <div class="font-semibold">{{ hoveredNode.name }}</div>
        <div class="text-mist-slate mt-0.5">
          <span
            class="inline-block w-1.5 h-1.5 rounded-full mr-1"
            :style="{ backgroundColor: getEntityColor(hoveredNode.entityType) }"
          />{{ hoveredNode.entityType }}
        </div>
        <div
          v-if="hoveredNode.sentiment !== undefined && hoveredNode.sentiment !== 0"
          class="mt-1 font-mono text-[11px]"
          :style="{ color: hoveredNode.sentiment > 0.2 ? '#6EE7B7' : hoveredNode.sentiment < -0.2 ? '#FF6B6B' : '#94A3B8' }"
        >
          {{ hoveredNode.sentiment > 0.2 ? 'Positive' : hoveredNode.sentiment < -0.2 ? 'Negative' : 'Neutral' }}
          {{ hoveredNode.sentiment > 0 ? '+' : '' }}{{ hoveredNode.sentiment.toFixed(2) }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'
import GraphCanvas from './GraphCanvas.vue'
import GraphControls from './GraphControls.vue'
import GraphSearchBar from './GraphSearchBar.vue'
import GraphLegend from './GraphLegend.vue'
import GraphDetailPanel from './GraphDetailPanel.vue'

const NODE_LIMIT = 50
const NODE_THRESHOLD = 100

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  metadata: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['node-selected'])

const canvasRef = ref(null)
const wrapperRef = ref(null)

const showEdgeLabels = ref(false)
const layoutName = ref('cose-bilkent')
const isFullscreen = ref(false)
const groupBy = ref('type')
const hiddenTypes = ref(new Set())
const selectedNode = ref(null)
const hoveredNode = ref(null)
const showAll = ref(false)

let hoverTimer = null

// All nodes regardless of filtering
const allNodes = computed(() => props.nodes || [])

// Smart filtering: if > NODE_THRESHOLD nodes, show top NODE_LIMIT by connection_count
const visibleNodes = computed(() => {
  const nodes = allNodes.value
  if (showAll.value || nodes.length <= NODE_THRESHOLD) return nodes
  return [...nodes]
    .sort((a, b) => (b.connection_count || 0) - (a.connection_count || 0))
    .slice(0, NODE_LIMIT)
})

const filterBanner = computed(() => {
  if (showAll.value || allNodes.value.length <= NODE_THRESHOLD) return ''
  return `Showing ${NODE_LIMIT} of ${allNodes.value.length} nodes.`
})

// Entity type summary from ALL nodes
const entityTypeSummary = computed(() => {
  const map = {}
  for (const node of allNodes.value) {
    const et = getPrimaryLabel(node.labels || ['Entity'])
    if (!map[et]) map[et] = { name: et, count: 0, color: getEntityColor(et) }
    map[et].count++
  }
  return Object.values(map).sort((a, b) => b.count - a.count)
})

function onNodeClick(data) {
  if (data) {
    selectedNode.value = data
    emit('node-selected', data.name)
  } else {
    selectedNode.value = null
  }
}

function onNodeHover(data) {
  clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => {
    hoveredNode.value = data
  }, 200)
}

function onNodeUnhover() {
  clearTimeout(hoverTimer)
  hoveredNode.value = null
}

function onCanvasReady() {
  // Canvas is ready
}

function onSearchSelect(uuid) {
  if (canvasRef.value) {
    canvasRef.value.focusNode(uuid)
  }
  // Find the node data and select it
  const node = allNodes.value.find((n) => n.uuid === uuid)
  if (node) {
    const entityType = getPrimaryLabel(node.labels || ['Entity'])
    selectedNode.value = {
      id: node.uuid,
      name: node.name || node.uuid,
      entityType,
      labels: (node.labels || []).join(', '),
      sentiment: node.sentiment ?? 0,
      summary: node.summary || '',
      connectionCount: node.connection_count || 0,
      relationships: node.relationships || [],
    }
    emit('node-selected', node.name)
  }
}

function onRefresh() {
  if (canvasRef.value) canvasRef.value.runLayout()
}

function onZoomFit() {
  const cy = canvasRef.value?.getCy?.()
  if (cy) cy.fit(undefined, 30)
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

function onEscKey(evt) {
  if (evt.key === 'Escape' && isFullscreen.value) {
    isFullscreen.value = false
  }
}

function toggleType(name) {
  const next = new Set(hiddenTypes.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  hiddenTypes.value = next
}

function showAllTypes() {
  hiddenTypes.value = new Set()
}

function hideAllTypes() {
  hiddenTypes.value = new Set(entityTypeSummary.value.map((et) => et.name))
}

function showAllNodes() {
  showAll.value = true
}

function navigateToNode(nodeId) {
  if (canvasRef.value) {
    canvasRef.value.focusNode(nodeId)
  }
  const node = allNodes.value.find((n) => n.uuid === nodeId)
  if (node) {
    const entityType = getPrimaryLabel(node.labels || ['Entity'])
    selectedNode.value = {
      id: node.uuid,
      name: node.name || node.uuid,
      entityType,
      labels: (node.labels || []).join(', '),
      sentiment: node.sentiment ?? 0,
      summary: node.summary || '',
      connectionCount: node.connection_count || 0,
      relationships: node.relationships || [],
    }
  }
}

function onExport() {
  if (!canvasRef.value) return
  const dataUrl = canvasRef.value.exportImage()
  if (!dataUrl) return
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = 'graph-export.png'
  a.click()
}

onMounted(() => {
  document.addEventListener('keydown', onEscKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onEscKey)
  clearTimeout(hoverTimer)
})
</script>

<style scoped>
.ambient-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.particle {
  position: absolute;
  border-radius: 50%;
  background: #22d3ee;
  animation: particle-drift ease-in-out infinite alternate;
}
@keyframes particle-drift {
  0% { transform: translate(0, 0) scale(1); opacity: 0.1; }
  50% { opacity: 0.3; }
  100% { transform: translate(12px, -18px) scale(1.4); opacity: 0.08; }
}
</style>
