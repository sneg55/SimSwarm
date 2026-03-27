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
    const size = Math.min(60, Math.max(20, 20 + connCount * 2))
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
    if (visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)) {
      elements.push({
        group: 'edges',
        data: {
          id: edge.id || `${edge.source}-${edge.target}-${edge.type}`,
          source: edge.source,
          target: edge.target,
          label: edge.type || '',
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
        'background-color': 'data(color)',
        width: 'data(size)',
        height: 'data(size)',
        label: 'data(label)',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 6,
        'font-size': 10,
        'font-family': 'Inter, system-ui, sans-serif',
        color: '#374151',
        'text-max-width': 80,
        'text-wrap': 'ellipsis',
        'border-width': 0,
        'border-color': '#7c3aed',
        'overlay-padding': 4,
        'transition-property': 'opacity, border-width, border-color',
        'transition-duration': '200ms',
      },
    },
    {
      selector: 'edge',
      style: {
        width: 1,
        'line-color': '#9ca3af',
        'target-arrow-color': '#9ca3af',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.6,
        'curve-style': 'bezier',
        label: props.showEdgeLabels ? 'data(label)' : '',
        'font-size': 8,
        color: '#6b7280',
        'text-rotation': 'autorotate',
        'text-margin-y': -8,
        opacity: 0.6,
        'transition-property': 'opacity, line-color',
        'transition-duration': '200ms',
      },
    },
    {
      selector: '.highlighted',
      style: {
        'border-width': 3,
        'border-color': '#7c3aed',
      },
    },
    {
      selector: '.neighbor',
      style: {
        opacity: 1,
      },
    },
    {
      selector: '.dimmed',
      style: {
        opacity: 0.2,
      },
    },
    {
      selector: '.selected-node',
      style: {
        'border-width': 3,
        'border-color': '#7c3aed',
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
  return cy.png({ full: true, scale: 2, bg: '#ffffff' })
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
