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

function getSentimentColor(sentiment) {
  if (sentiment > 0.2) return '#6EE7B7'   // positive — green
  if (sentiment < -0.2) return '#FF6B6B'  // negative — red
  return '#94A3B8'                         // neutral — gray
}

function buildElements() {
  const elements = []
  const visibleNodeIds = new Set()

  for (const node of props.nodes) {
    const entityType = getPrimaryLabel(node.labels || ['Entity'])
    if (props.hiddenTypes.has(entityType)) continue
    visibleNodeIds.add(node.uuid)
    const connCount = node.connection_count || 0
    const sentiment = node.sentiment ?? 0
    // Size scales with connections + sentiment intensity
    const sentScale = 1 + Math.abs(sentiment) * 0.3
    const size = Math.min(70, Math.max(28, (28 + Math.sqrt(connCount) * 8) * sentScale))
    elements.push({
      group: 'nodes',
      data: {
        id: node.uuid,
        label: node.name || node.uuid,
        color: getEntityColor(entityType),
        sentimentColor: getSentimentColor(sentiment),
        sentiment,
        size,
        entityType,
        labels: (node.labels || []).join(', '),
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
        // Concentric ring: dark center + entity-colored inner ring + sentiment outer glow
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
        // Inner entity-colored ring
        'border-width': 4,
        'border-color': 'data(color)',
        'border-opacity': 0.9,
        'overlay-padding': 6,
        // Outer glow uses sentiment color (falls back to entity color if no sentiment)
        'shadow-blur': 25,
        'shadow-color': 'data(sentimentColor)',
        'shadow-opacity': 0.5,
        'shadow-offset-x': 0,
        'shadow-offset-y': 0,
        // Inner dot via pie chart
        'pie-size': '40%',
        'pie-1-background-color': 'data(color)',
        'pie-1-background-size': 100,
        'pie-1-background-opacity': 0.9,
        'transition-property': 'opacity, border-width, border-color, shadow-blur, shadow-opacity',
        'transition-duration': '300ms',
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
        // Labels hidden by default, shown on hover via class
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
      // Hovered edge — show label + highlight
      selector: 'edge.hover-edge',
      style: {
        label: 'data(label)',
        width: 3,
        'line-color': '#64748B',
        'line-opacity': 0.8,
        'target-arrow-color': '#94A3B8',
        color: '#E2E8F0',
        'font-size': 10,
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
      // Edges connected to highlighted node — show labels
      selector: '.highlighted-edge',
      style: {
        label: 'data(label)',
        width: 3,
        'line-color': '#22D3EE',
        'line-opacity': 0.9,
        'target-arrow-color': '#22D3EE',
        color: '#E2E8F0',
        'font-size': 10,
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

  // Re-fit after layout completes and start ambient glow animation
  cy.on('layoutstop', () => {
    cy.fit(undefined, 30)
    startAmbientAnimation()
  })

  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    const data = node.data()
    emit('node-click', {
      id: data.id,
      name: data.label,
      entityType: data.entityType,
      labels: data.labels,
      sentiment: data.sentiment,
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
      sentiment: data.sentiment,
      x: pos.x,
      y: pos.y,
    })

    // Dim non-neighbors, highlight connected edges with labels
    const neighborhood = node.neighborhood().add(node)
    cy.elements().addClass('dimmed')
    neighborhood.removeClass('dimmed').addClass('neighbor')
    node.connectedEdges().addClass('highlighted-edge').removeClass('dimmed')
    node.addClass('highlighted')
  })

  cy.on('mouseout', 'node', () => {
    emit('node-unhover')
    cy.elements().removeClass('dimmed neighbor highlighted highlighted-edge')
  })

  // Pause drift when user grabs a node, update anchor on release
  cy.on('grab', 'node', () => { stopAmbientAnimation() })
  cy.on('free', 'node', (evt) => {
    const node = evt.target
    if (nodeAnchors) {
      const pos = node.position()
      const a = nodeAnchors.get(node.id())
      if (a) { a.x = pos.x; a.y = pos.y }
    }
    startAmbientAnimation()
  })

  // Edge hover — show label on individual edge
  cy.on('mouseover', 'edge', (evt) => {
    evt.target.addClass('hover-edge')
  })
  cy.on('mouseout', 'edge', (evt) => {
    evt.target.removeClass('hover-edge')
  })

  emit('ready')
}

let animFrame = null
let nodeAnchors = null

function startAmbientAnimation() {
  // Store each node's layout position as its "anchor"
  if (!cy) return
  nodeAnchors = new Map()
  cy.nodes().forEach((node, i) => {
    const pos = node.position()
    nodeAnchors.set(node.id(), {
      x: pos.x, y: pos.y,
      phase: i * 1.3,       // offset so nodes drift differently
      speed: 0.3 + (i % 5) * 0.1,
      radius: 3 + (i % 4) * 1.5,
    })
  })

  function tick() {
    if (!cy || !nodeAnchors) return
    const t = Date.now() / 1000
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const a = nodeAnchors.get(node.id())
        if (!a) return
        // Gentle drift around anchor
        const dx = Math.sin(t * a.speed + a.phase) * a.radius
        const dy = Math.cos(t * a.speed * 0.7 + a.phase + 1.5) * a.radius
        node.position({ x: a.x + dx, y: a.y + dy })
        // Glow pulse
        const glowPhase = (t + a.phase) % (Math.PI * 2)
        node.style({
          'shadow-blur': 20 + Math.sin(glowPhase) * 10,
          'shadow-opacity': 0.5 + Math.sin(glowPhase) * 0.2,
        })
      })
    })
    animFrame = requestAnimationFrame(tick)
  }
  tick()
}

function stopAmbientAnimation() {
  if (animFrame) cancelAnimationFrame(animFrame)
  animFrame = null
  nodeAnchors = null
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
  stopAmbientAnimation()
  if (cy) {
    cy.destroy()
    cy = null
  }
})
</script>
