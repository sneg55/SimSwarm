import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

const NODE_LIMIT = 50
const NODE_THRESHOLD = 100

/**
 * Builds a node selection object from raw node data.
 */
function buildNodeSelection(node) {
  const entityType = getPrimaryLabel(node.labels || ['Entity'])
  return {
    id: node.uuid,
    name: node.name || node.uuid,
    entityType,
    labels: (node.labels || []).join(', '),
    sentiment: node.sentiment ?? 0,
    stance: node.stance || null,
    influenceWeight: node.influence_weight ?? null,
    summary: node.summary || '',
    connectionCount: node.connection_count || 0,
    relationships: node.relationships || [],
  }
}

export function useGraphVisualization(props, emit) {
  const canvasRef = ref(null)
  const wrapperRef = ref(null)

  const showEdgeLabels = ref(false)
  const layoutName = ref('cose-bilkent')
  const isFullscreen = ref(false)
  const groupBy = ref('type')
  const hiddenTypes = ref(new Set())
  const hiddenSentiments = ref(new Set())
  const selectedNode = ref(null)
  const hoveredNode = ref(null)
  const showAll = ref(false)

  let hoverTimer = null

  const allNodes = computed(() => props.nodes || [])

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

  const entityTypeSummary = computed(() => {
    const map = {}
    for (const node of allNodes.value) {
      const et = getPrimaryLabel(node.labels || ['Entity'])
      if (!map[et]) map[et] = { name: et, count: 0, color: getEntityColor(et) }
      map[et].count++
    }
    return Object.values(map).sort((a, b) => b.count - a.count)
  })

  const agentActions = computed(() => {
    if (!selectedNode.value || !props.chatLog.length) return []
    const name = selectedNode.value.name
    return props.chatLog.filter(e => e.agent_name === name)
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
    hoverTimer = setTimeout(() => { hoveredNode.value = data }, 200)
  }

  function onNodeUnhover() {
    clearTimeout(hoverTimer)
    hoveredNode.value = null
  }

  function onCanvasReady() {}

  function onSearchSelect(uuid) {
    if (canvasRef.value) canvasRef.value.focusNode(uuid)
    const node = allNodes.value.find((n) => n.uuid === uuid)
    if (node) {
      selectedNode.value = buildNodeSelection(node)
      emit('node-selected', node.name)
    }
  }

  function onRefresh() {
    if (canvasRef.value) canvasRef.value.runLayout()
  }

  function onZoomFit() {
    if (canvasRef.value) canvasRef.value.fitToVisibleArea()
  }

  function toggleFullscreen() {
    isFullscreen.value = !isFullscreen.value
  }

  function onEscKey(evt) {
    if (evt.key === 'Escape' && isFullscreen.value) isFullscreen.value = false
  }

  function toggleType(name) {
    const next = new Set(hiddenTypes.value)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    hiddenTypes.value = next
  }

  function toggleSentiment(bucket) {
    const next = new Set(hiddenSentiments.value)
    if (next.has(bucket)) next.delete(bucket)
    else next.add(bucket)
    hiddenSentiments.value = next
  }

  function showAllTypes() { hiddenTypes.value = new Set() }

  function hideAllTypes() {
    hiddenTypes.value = new Set(entityTypeSummary.value.map((et) => et.name))
  }

  function showAllNodes() { showAll.value = true }

  function navigateToNode(nodeId) {
    if (canvasRef.value) canvasRef.value.focusNode(nodeId)
    const node = allNodes.value.find((n) => n.uuid === nodeId)
    if (node) selectedNode.value = buildNodeSelection(node)
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

  onMounted(() => { document.addEventListener('keydown', onEscKey) })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', onEscKey)
    clearTimeout(hoverTimer)
  })

  return {
    canvasRef, wrapperRef,
    showEdgeLabels, layoutName, isFullscreen, groupBy,
    hiddenTypes, hiddenSentiments, selectedNode, hoveredNode,
    allNodes, visibleNodes, filterBanner, entityTypeSummary, agentActions,
    onNodeClick, onNodeHover, onNodeUnhover, onCanvasReady,
    onSearchSelect, onRefresh, onZoomFit, toggleFullscreen,
    toggleType, toggleSentiment, showAllTypes, hideAllTypes, showAllNodes,
    navigateToNode, onExport,
  }
}
