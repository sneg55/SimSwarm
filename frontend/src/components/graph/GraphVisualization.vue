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
        :hidden-sentiments="hiddenSentiments"
        :show-edge-labels="showEdgeLabels"
        :layout-name="layoutName"
        :selected-node-id="selectedNode?.id || null"
        :panel-open="!!selectedNode"
        @node-click="onNodeClick"
        @node-hover="onNodeHover"
        @node-unhover="onNodeUnhover"
        @ready="onCanvasReady"
      />

      <!-- Unified toolbar bar -->
      <div class="absolute top-0 left-0 right-0 z-10 flex items-center gap-2 px-3 py-2 glass border-b border-mist-depth/50">
        <GraphSearchBar
          :nodes="allNodes"
          @select-node="onSearchSelect"
        />
        <div class="flex-1" />
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
      <div class="absolute bottom-14 left-3 z-10">
        <GraphLegend
          :entity-types="entityTypeSummary"
          :hidden-types="hiddenTypes"
          :hidden-sentiments="hiddenSentiments"
          :filter-banner="filterBanner"
          :nodes="allNodes"
          @toggle-type="toggleType"
          @toggle-sentiment="toggleSentiment"
          @show-all="showAllTypes"
          @hide-all="hideAllTypes"
          @show-all-nodes="showAllNodes"
        />
      </div>

      <!-- Detail panel (right side) -->
      <GraphDetailPanel
        :node="selectedNode"
        :agent-actions="agentActions"
        @close="selectedNode = null"
        @navigate-to="navigateToNode"
      />

      <!-- Hover tooltip -->
      <div
        v-if="hoveredNode"
        class="absolute pointer-events-none z-20 text-mist-foam text-xs rounded-lg px-3 py-2 border"
        :style="{
          left: hoveredNode.x + 12 + 'px',
          top: hoveredNode.y - 8 + 'px',
          background: 'rgba(10,20,30,0.92)',
          borderColor: 'rgba(34,211,238,0.2)',
          boxShadow: '0 10px 40px rgba(8,47,73,0.3)',
          maxWidth: '240px',
        }"
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
        <div v-if="hoveredNode.stance && hoveredNode.stance !== 'neutral'" class="mt-0.5 text-[11px] text-mist-drift capitalize">
          {{ hoveredNode.stance }}
        </div>
        <div class="border-t mt-1.5 pt-1.5" style="border-color: rgba(34,211,238,0.1);">
          <div class="text-gray-400 text-[10px] leading-relaxed">{{ getTooltip('graphVisualization.hoverMeaning')?.meaning }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { getEntityColor } from './graphColors.js'
import GraphCanvas from './GraphCanvas.vue'
import GraphControls from './GraphControls.vue'
import GraphSearchBar from './GraphSearchBar.vue'
import GraphLegend from './GraphLegend.vue'
import GraphDetailPanel from './GraphDetailPanel.vue'
import { getTooltip } from '../../data/tooltipCopy.js'
import { useGraphVisualization } from './useGraphVisualization.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  metadata: { type: Object, default: () => ({}) },
  chatLog: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['node-selected'])

const {
  canvasRef, wrapperRef,
  showEdgeLabels, layoutName, isFullscreen, groupBy,
  hiddenTypes, hiddenSentiments, selectedNode, hoveredNode,
  allNodes, visibleNodes, filterBanner, entityTypeSummary, agentActions,
  onNodeClick, onNodeHover, onNodeUnhover, onCanvasReady,
  onSearchSelect, onRefresh, onZoomFit, toggleFullscreen,
  toggleType, toggleSentiment, showAllTypes, hideAllTypes, showAllNodes,
  navigateToNode, onExport,
} = useGraphVisualization(props, emit)

defineExpose({ exportImage: onExport })
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
