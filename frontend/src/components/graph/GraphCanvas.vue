<template>
  <div ref="containerRef" class="w-full h-full"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import dagre from 'cytoscape-dagre'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

cytoscape.use(coseBilkent)
cytoscape.use(dagre)

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'cose-bilkent' },
  selectedNodeId: { type: String, default: null },
})

const emit = defineEmits(['node-click', 'node-hover', 'node-unhover', 'ready'])

const containerRef = ref(null)
let cy = null

const LAYOUT_OPTIONS = {
  'cose-bilkent': {
    name: 'cose-bilkent',
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
    edgeElasticity: 0.1,
    nestingFactor: 0.1,
    gravity: 0.25,
    numIter: 2500,
    animate: 'end',
    animationDuration: 500,
    fit: true,
    padding: 30,
  },
  circle: {
    name: 'circle',
    animate: true,
    animationDuration: 500,
    fit: true,
    padding: 30,
  },
  dagre: {
    name: 'dagre',
    rankDir: 'TB',
    animate: true,
    animationDuration: 500,
    fit: true,
    padding: 30,
  },
  grid: {
    name: 'grid',
    animate: true,
    animationDuration: 500,
    fit: true,
    padding: 30,
  },
}

function buildElements() {
  const elements = []
  const visibleNodeIds = new Set()

  for (const node of props.nodes) {
    const entityType = getPrimaryLabel(node.labels || ['Entity'])
    if (props.hiddenTypes.has(entityType)) continue
    visibleNodeIds.add(node.uuid)
    const connCount = node.connection_count || 0
    const size = Math.min(65, Math.max(28, 28 + Math.sqrt(connCount) * 8))
    elements.push({
      group: 'nodes',
      data: {
        id: node.uuid,
        label: node.name || node.uuid,
        color: getEntityColor(entityType),
        size,
        entityType,
        summary: node.summary || '',
        connectionCount: connCount,
        relationships: node.relationships || [],
      },
    })
  }

  for (const edge of props.edges) {
    if (visibleNodeIds.has(edge.source_node_uuid) && visibleNodeIds.has(edge.target_node_uuid)) {
      elements.push({
        group: 'edges',
        data: {
          id: edge.uuid || `e-${edge.source_node_uuid}-${edge.target_node_uuid}`,
          source: edge.source_node_uuid,
          target: edge.target_node_uuid,
          label: edge.name || edge.fact || '',
        },
      })
    }
  }

  return elements
}

function getStylesheet() {
  return [
    {
      selector: 'node',
      style: {
        // Concentric ring effect: dark fill + colored wide border + glow
        'background-color': '#0B1120',
        'background-opacity': 0.7,
        width: 'data(size)',
        height: 'data(size)',
        label: 'data(label)',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 10,
        'font-size': 13,
        'font-weight': 600,
        'font-family': 'Inter, system-ui, sans-serif',
        color: '#E2E8F0',
        'text-outline-color': '#0B1120',
        'text-outline-width': 2.5,
        'text-max-width': 130,
        'text-wrap': 'ellipsis',
        // Thick colored ring border
        'border-width': 4,
        'border-color': 'data(color)',
        'border-opacity': 0.9,
        'overlay-padding': 6,
        // Bioluminescent glow
        'shadow-blur': 25,
        'shadow-color': 'data(color)',
        'shadow-opacity': 0.6,
        'shadow-offset-x': 0,
        'shadow-offset-y': 0,
        'transition-property': 'opacity, border-width, border-color, shadow-blur, shadow-opacity',
        'transition-duration': '300ms',
      },
    },
    {
      // Inner dot via :active pseudo-style workaround — use a second style for nodes
      // Cytoscape doesn't support pseudo-elements, so we use pie-chart background
      // to simulate the inner dot
      selector: 'node',
      style: {
        'pie-size': '40%',
        'pie-1-background-color': 'data(color)',
        'pie-1-background-size': 100,
        'pie-1-background-opacity': 0.9,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 2,
        'line-color': '#334155',
        'line-opacity': 0.4,
        'target-arrow-color': '#475569',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.8,
        'curve-style': 'bezier',
        label: props.showEdgeLabels ? 'data(label)' : '',
        'font-size': 9,
        color: '#94A3B8',
        'text-rotation': 'autorotate',
        'text-margin-y': -10,
        'text-outline-color': '#0B1120',
        'text-outline-width': 2,
        'transition-property': 'opacity, line-color, width',
        'transition-duration': '300ms',
      },
    },
    {
      selector: '.highlighted',
      style: {
        'border-width': 5,
        'border-opacity': 1,
        'shadow-blur': 45,
        'shadow-opacity': 0.9,
      },
    },
    {
      selector: '.highlighted-edge',
      style: {
        width: 3,
        'line-color': '#22D3EE',
        'line-opacity': 0.9,
        'target-arrow-color': '#22D3EE',
      },
    },
    {
      selector: '.neighbor',
      style: {
        opacity: 1,
        'shadow-blur': 30,
        'shadow-opacity': 0.7,
      },
    },
    {
      selector: '.dimmed',
      style: {
        opacity: 0.12,
      },
    },
    {
      selector: '.selected-node',
      style: {
        'border-width': 5,
        'border-color': '#A78BFA',
        'border-opacity': 1,
        'shadow-blur': 55,
        'shadow-color': '#A78BFA',
        'shadow-opacity': 0.8,
      },
    },
  ]
}

function initCytoscape() {
  if (!containerRef.value) return
  if (cy) cy.destroy()

  cy = cytoscape({
    container: containerRef.value,
    elements: buildElements(),
    style: getStylesheet(),
    layout: LAYOUT_OPTIONS[props.layoutName] || LAYOUT_OPTIONS['cose-bilkent'],
    minZoom: 0.1,
    maxZoom: 5,
    wheelSensitivity: 0.3,
  })

  // Re-fit after layout completes — handles case where container
  // dimensions aren't final when the initial layout runs
  cy.on('layoutstop', () => {
    cy.fit(undefined, 30)
  })

  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    const data = node.data()
    emit('node-click', {
      id: data.id,
      name: data.label,
      entityType: data.entityType,
      summary: data.summary,
      connectionCount: data.connectionCount,
      relationships: data.relationships,
    })
  })

  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      emit('node-click', null)
    }
  })

  cy.on('mouseover', 'node', (evt) => {
    const node = evt.target
    const data = node.data()
    const pos = evt.renderedPosition
    emit('node-hover', {
      name: data.label,
      entityType: data.entityType,
      x: pos.x,
      y: pos.y,
    })

    // Dim non-neighbors
    const neighborhood = node.neighborhood().add(node)
    cy.elements().addClass('dimmed')
    neighborhood.removeClass('dimmed').addClass('neighbor')
    node.addClass('highlighted')
  })

  cy.on('mouseout', 'node', () => {
    emit('node-unhover')
    cy.elements().removeClass('dimmed neighbor highlighted')
  })

  emit('ready')
}

function runLayout(name) {
  if (!cy) return
  const opts = LAYOUT_OPTIONS[name || props.layoutName] || LAYOUT_OPTIONS['cose-bilkent']
  cy.layout(opts).run()
}

function focusNode(id) {
  if (!cy) return
  const node = cy.getElementById(id)
  if (node && node.length) {
    cy.animate({
      center: { eles: node },
      zoom: 2,
    }, { duration: 400 })
    cy.elements().removeClass('selected-node')
    node.addClass('selected-node')
  }
}

function exportImage() {
  if (!cy) return null
  return cy.png({ full: true, scale: 2, bg: '#0B1120' })
}

function getCy() {
  return cy
}

defineExpose({ runLayout, focusNode, exportImage, getCy })

// Watch hiddenTypes → rebuild elements
watch(() => props.hiddenTypes, () => {
  if (!cy) return
  cy.json({ elements: buildElements() })
  cy.style(getStylesheet())
  runLayout()
}, { deep: true })

// Watch layoutName → rerun layout
watch(() => props.layoutName, (name) => {
  runLayout(name)
})

// Watch showEdgeLabels → update edge style
watch(() => props.showEdgeLabels, () => {
  if (!cy) return
  cy.style(getStylesheet())
})

// Watch selectedNodeId → focus node
watch(() => props.selectedNodeId, (id) => {
  if (id) focusNode(id)
  else if (cy) cy.elements().removeClass('selected-node')
})

// Watch nodes/edges → rebuild
watch([() => props.nodes, () => props.edges], () => {
  if (cy) {
    cy.json({ elements: buildElements() })
    cy.style(getStylesheet())
    runLayout()
  }
}, { deep: true })

onMounted(() => {
  nextTick(() => initCytoscape())
})

onBeforeUnmount(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})
</script>
