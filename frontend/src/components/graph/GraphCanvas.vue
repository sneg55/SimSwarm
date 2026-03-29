<template>
  <div ref="containerRef" class="w-full h-full" style="position:relative;">
    <canvas ref="canvasRef" class="w-full h-full" style="display:block;" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { getEntityColor, getPrimaryLabel } from './graphColors.js'

const PANEL_WIDTH = 320 // w-80 = 20rem

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  hiddenTypes: { type: Set, default: () => new Set() },
  showEdgeLabels: { type: Boolean, default: false },
  layoutName: { type: String, default: 'force' },
  selectedNodeId: { type: String, default: null },
  panelOpen: { type: Boolean, default: false },
})

const emit = defineEmits(['node-click', 'node-hover', 'node-unhover', 'ready'])

const containerRef = ref(null)
const canvasRef = ref(null)

// Internal state
let ctx = null
let dpr = 1
let W = 0, H = 0
let graphNodes = []
let graphEdges = []
let hoveredNode = null
let selectedNode = null
const connectedIds = new Set()
let highlightedNodeId = null
let highlightStartTime = 0
let animFrame = null
let lastTime = 0

const SENTIMENT_COLORS = {
  negative: { r: 255, g: 107, b: 107 },
  positive: { r: 110, g: 231, b: 183 },
  neutral:  { r: 148, g: 163, b: 184 },
}

function parseColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
}

function getSentimentColor(s) {
  if (s > 0.2) return SENTIMENT_COLORS.positive
  if (s < -0.2) return SENTIMENT_COLORS.negative
  return SENTIMENT_COLORS.neutral
}

function resize() {
  if (!canvasRef.value || !containerRef.value) return
  W = containerRef.value.clientWidth
  H = containerRef.value.clientHeight
  dpr = window.devicePixelRatio || 1
  canvasRef.value.width = W * dpr
  canvasRef.value.height = H * dpr
  canvasRef.value.style.width = W + 'px'
  canvasRef.value.style.height = H + 'px'
  ctx = canvasRef.value.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function buildGraph() {
  if (!W || !H) return
  graphNodes = []
  graphEdges = []

  // Group nodes by entity type for clustering
  const typeGroups = {}
  for (const node of props.nodes) {
    const et = getPrimaryLabel(node.labels || ['Entity'])
    if (!typeGroups[et]) typeGroups[et] = []
    typeGroups[et].push(node)
  }

  const typeNames = Object.keys(typeGroups)
  const clusterCount = typeNames.length || 1

  // Create cluster centers in a circle — use available width (excluding panel)
  const rightBound = props.panelOpen ? W - PANEL_WIDTH : W
  const centerX = rightBound / 2 / W  // proportional center of available area
  const clusters = typeNames.map((_, i) => ({
    x: centerX + Math.cos((i / clusterCount) * Math.PI * 2 - Math.PI / 2) * 0.2,
    y: 0.5 + Math.sin((i / clusterCount) * Math.PI * 2 - Math.PI / 2) * 0.2,
  }))

  const nodeIdMap = {}

  typeNames.forEach((type, typeIdx) => {
    const group = typeGroups[type]
    const cc = clusters[typeIdx]
    const colorHex = getEntityColor(type)
    const color = parseColor(colorHex)

    group.forEach((node, i) => {
      const connCount = node.connection_count || 0
      const sentiment = node.sentiment ?? 0
      const baseSize = 4 + Math.sqrt(connCount + 1) * 3
      const angle = (i / group.length) * Math.PI * 2 + Math.random() * 0.5
      const radius = 0.03 + Math.random() * 0.05

      const gn = {
        id: node.uuid,
        x: (cc.x + Math.cos(angle) * radius) * W,
        y: (cc.y + Math.sin(angle) * radius) * H,
        vx: 0, vy: 0,
        homeX: cc.x + Math.cos(angle) * radius * 0.6,
        homeY: cc.y + Math.sin(angle) * radius * 0.6,
        size: baseSize,
        color,
        colorHex,
        type,
        name: node.name || node.uuid,
        sentiment,
        sentimentColor: getSentimentColor(sentiment),
        phase: Math.random() * Math.PI * 2,
        connectionCount: connCount,
        summary: node.summary || '',
        labels: (node.labels || []).join(', '),
        relationships: node.relationships || [],
      }
      graphNodes.push(gn)
      nodeIdMap[node.uuid] = gn
    })
  })

  // Build edges
  const nodeIndexMap = {}
  graphNodes.forEach((n, i) => { nodeIndexMap[n.id] = i })

  for (const edge of props.edges) {
    const fromIdx = nodeIndexMap[edge.source_node_uuid]
    const toIdx = nodeIndexMap[edge.target_node_uuid]
    if (fromIdx !== undefined && toIdx !== undefined) {
      graphEdges.push({
        from: fromIdx,
        to: toIdx,
        label: edge.name || edge.fact || '',
      })
    }
  }
}

// Mouse tracking
let mouseX = -1, mouseY = -1

function onMouseMove(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  mouseX = e.clientX - rect.left
  mouseY = e.clientY - rect.top

  const prev = hoveredNode
  hoveredNode = null
  for (const n of graphNodes) {
    if (props.hiddenTypes.has(n.type)) continue
    const dx = n.x - mouseX, dy = n.y - mouseY
    if (Math.sqrt(dx * dx + dy * dy) < n.size * 1.5 + 8) {
      hoveredNode = n
      break
    }
  }

  if (hoveredNode) {
    canvasRef.value.style.cursor = 'pointer'
    emit('node-hover', {
      name: hoveredNode.name,
      entityType: hoveredNode.type,
      sentiment: hoveredNode.sentiment,
      x: mouseX,
      y: mouseY,
    })
  } else {
    canvasRef.value.style.cursor = 'default'
    if (prev) emit('node-unhover')
  }
}

function onClick() {
  if (hoveredNode) {
    selectedNode = hoveredNode
    connectedIds.clear()
    connectedIds.add(hoveredNode.id)
    for (const e of graphEdges) {
      if (graphNodes[e.from] === hoveredNode) connectedIds.add(graphNodes[e.to].id)
      if (graphNodes[e.to] === hoveredNode) connectedIds.add(graphNodes[e.from].id)
    }
    emit('node-click', {
      id: hoveredNode.id,
      name: hoveredNode.name,
      entityType: hoveredNode.type,
      labels: hoveredNode.labels,
      sentiment: hoveredNode.sentiment,
      summary: hoveredNode.summary,
      connectionCount: hoveredNode.connectionCount,
      relationships: hoveredNode.relationships,
    })
  } else {
    selectedNode = null
    connectedIds.clear()
    emit('node-click', null)
  }
}

function animate(timestamp) {
  if (!ctx || !W || !H) { animFrame = requestAnimationFrame(animate); return }

  const time = timestamp * 0.001
  const dt = Math.min(time - lastTime, 0.05)
  lastTime = time
  ctx.clearRect(0, 0, W, H)

  // Physics
  for (let i = 0; i < graphNodes.length; i++) {
    const n = graphNodes[i]
    if (props.hiddenTypes.has(n.type)) continue

    // Home pull
    n.vx += (n.homeX * W - n.x) * 0.00008
    n.vy += (n.homeY * H - n.y) * 0.00008
    // Organic drift
    n.vx += Math.sin(time * 0.3 + n.phase) * 0.006
    n.vy += Math.cos(time * 0.25 + n.phase * 1.3) * 0.006

    // Repulsion
    for (let j = i + 1; j < graphNodes.length; j++) {
      const m = graphNodes[j]
      if (props.hiddenTypes.has(m.type)) continue
      const dx = m.x - n.x, dy = m.y - n.y
      const d = Math.sqrt(dx * dx + dy * dy)
      const minDist = (n.size + m.size) * 3
      if (d < minDist && d > 0.5) {
        const force = 0.12 * (1 - d / minDist)
        n.vx -= (dx / d) * force
        n.vy -= (dy / d) * force
        m.vx += (dx / d) * force
        m.vy += (dy / d) * force
      }
    }

    n.vx *= 0.985
    n.vy *= 0.985
    n.x += n.vx
    n.y += n.vy

    // Bounds — keep nodes within visible area (left of panel when open)
    const rBound = props.panelOpen ? W - PANEL_WIDTH - 40 : W - 40
    if (n.x < 40) n.vx += 0.08
    if (n.x > rBound) n.vx -= 0.08
    if (n.y < 40) n.vy += 0.08
    if (n.y > H - 40) n.vy -= 0.08
  }

  // Draw edges
  for (const e of graphEdges) {
    const a = graphNodes[e.from], b = graphNodes[e.to]
    if (props.hiddenTypes.has(a.type) || props.hiddenTypes.has(b.type)) continue
    const isHighlighted = selectedNode && (a === selectedNode || b === selectedNode)
    const isPinged = highlightedNodeId !== null && (a.id === highlightedNodeId || b.id === highlightedNodeId)
    const active = isHighlighted || isPinged

    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
    const mr = (a.color.r + b.color.r) >> 1
    const mg = (a.color.g + b.color.g) >> 1
    const mb = (a.color.b + b.color.b) >> 1
    ctx.strokeStyle = `rgba(${mr},${mg},${mb},${active ? 0.5 : 0.1})`
    ctx.lineWidth = isPinged ? 2 : isHighlighted ? 1.5 : 0.5
    ctx.stroke()

    // Edge labels
    if (active && e.label && props.showEdgeLabels) {
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
      ctx.font = '9px Inter'
      ctx.fillStyle = 'rgba(148,163,184,0.7)'
      ctx.textAlign = 'center'
      ctx.fillText(e.label, mx, my - 4)
    }
  }

  // Draw nodes
  for (const n of graphNodes) {
    const isHidden = props.hiddenTypes.has(n.type)
    const isSelected = n === selectedNode
    const isHovered = n === hoveredNode
    const isConnected = connectedIds.has(n.id)
    const isPinged = n.id === highlightedNodeId
    const pulse = 1 + Math.sin(time * 1.5 + n.phase) * 0.08
    const sentScale = 1 + Math.abs(n.sentiment) * 0.4
    const s = n.size * pulse * sentScale * (isHovered ? 1.3 : 1) * (isSelected ? 1.2 : 1)
    const fadeMul = isHidden ? 0.08 : 1

    // Glow
    if (!isHidden) {
      const glowAlpha = isPinged ? 0.5 : isSelected ? 0.4 : isConnected ? 0.3 : isHovered ? 0.25 : 0.12
      const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, s * 4)
      grad.addColorStop(0, `rgba(${n.color.r},${n.color.g},${n.color.b},${glowAlpha})`)
      grad.addColorStop(1, `rgba(${n.color.r},${n.color.g},${n.color.b},0)`)
      ctx.beginPath()
      ctx.arc(n.x, n.y, s * 4, 0, Math.PI * 2)
      ctx.fillStyle = grad
      ctx.fill()
    }

    // Core circle
    let coreAlpha
    if (selectedNode && !isConnected && !isSelected && !isPinged) {
      coreAlpha = 0.15 * fadeMul
    } else {
      coreAlpha = (isSelected || isHovered ? 1 : 0.8) * fadeMul
    }
    ctx.beginPath()
    ctx.arc(n.x, n.y, s, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${n.color.r},${n.color.g},${n.color.b},${coreAlpha})`
    ctx.fill()

    // Sentiment ring
    if (!isHidden && Math.abs(n.sentiment) > 0.15) {
      const sc = n.sentimentColor
      const intensity = Math.abs(n.sentiment)
      const ringWidth = 1 + intensity * 3
      const ringGap = 2 + ringWidth
      const ringAlpha = (0.25 + intensity * 0.55) * fadeMul

      if (intensity > 0.5) {
        const glowR = s + ringGap + ringWidth + 4
        const sentGlow = ctx.createRadialGradient(n.x, n.y, s + ringGap, n.x, n.y, glowR)
        sentGlow.addColorStop(0, `rgba(${sc.r},${sc.g},${sc.b},${intensity * 0.15 * fadeMul})`)
        sentGlow.addColorStop(1, `rgba(${sc.r},${sc.g},${sc.b},0)`)
        ctx.beginPath()
        ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2)
        ctx.fillStyle = sentGlow
        ctx.fill()
      }

      ctx.beginPath()
      ctx.arc(n.x, n.y, s + ringGap, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(${sc.r},${sc.g},${sc.b},${ringAlpha})`
      ctx.lineWidth = ringWidth
      ctx.stroke()
    }

    // Bright center dot
    if (s > 4 && !isHidden) {
      ctx.beginPath()
      ctx.arc(n.x, n.y, s * 0.3, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255,255,255,${isSelected ? 0.5 : 0.25})`
      ctx.fill()
    }

    // Ping animation
    if (n.id === highlightedNodeId && !isHidden) {
      const elapsed = time - highlightStartTime
      for (let ring = 0; ring < 3; ring++) {
        const ringTime = (elapsed - ring * 0.4) % 2
        if (ringTime > 0 && ringTime < 1.5) {
          const progress = ringTime / 1.5
          const ringR = s + 8 + progress * 30
          const ringA = (1 - progress) * 0.5
          ctx.beginPath()
          ctx.arc(n.x, n.y, ringR, 0, Math.PI * 2)
          ctx.strokeStyle = `rgba(${n.color.r},${n.color.g},${n.color.b},${ringA})`
          ctx.lineWidth = 2 * (1 - progress)
          ctx.stroke()
        }
      }
    }

    // Label
    const showLabel = (isSelected || isHovered || isConnected || isPinged || (!selectedNode && s > 6)) && !isHidden
    if (showLabel && n.name) {
      ctx.font = isSelected ? 'bold 12px Inter' : '11px Inter'
      const labelAlpha = isSelected ? 1 : isConnected ? 0.85 : isHovered ? 0.9 : 0.45
      ctx.fillStyle = `rgba(241,245,249,${labelAlpha})`
      ctx.textAlign = 'center'
      ctx.fillText(n.name, n.x, n.y + s + 14)
    }
  }

  animFrame = requestAnimationFrame(animate)
}

// Public methods
function runLayout() {
  buildGraph()
}

function fitToVisibleArea() {
  if (!graphNodes.length || !W || !H) return
  const rightBound = props.panelOpen ? W - PANEL_WIDTH : W
  const margin = 50

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of graphNodes) {
    if (props.hiddenTypes.has(n.type)) continue
    minX = Math.min(minX, n.x)
    maxX = Math.max(maxX, n.x)
    minY = Math.min(minY, n.y)
    maxY = Math.max(maxY, n.y)
  }
  if (minX === Infinity) return

  const bbW = maxX - minX || 1
  const bbH = maxY - minY || 1
  const availW = rightBound - margin * 2
  const availH = H - margin * 2
  const scale = Math.min(availW / bbW, availH / bbH, 1)
  const bbCx = (minX + maxX) / 2
  const bbCy = (minY + maxY) / 2
  const targetCx = margin + availW / 2
  const targetCy = margin + availH / 2

  for (const n of graphNodes) {
    n.x = (n.x - bbCx) * scale + targetCx
    n.y = (n.y - bbCy) * scale + targetCy
    n.homeX = n.x / W
    n.homeY = n.y / H
  }
}

function focusNode(id) {
  const node = graphNodes.find(n => n.id === id)
  if (!node) return
  highlightedNodeId = id
  highlightStartTime = performance.now() * 0.001
  // Pan node to center of available area (left of panel)
  const rightBound = props.panelOpen ? W - PANEL_WIDTH : W
  const cx = rightBound / 2, cy2 = H / 2
  const dx = cx - node.x, dy = cy2 - node.y
  for (const n of graphNodes) {
    n.x += dx; n.y += dy
    n.homeX += dx / W; n.homeY += dy / H
  }
  // Clear ping after 4s
  setTimeout(() => { if (highlightedNodeId === id) highlightedNodeId = null }, 4000)
}

function exportImage() {
  if (!canvasRef.value) return null
  return canvasRef.value.toDataURL('image/png')
}

function getCy() { return null }

defineExpose({ runLayout, focusNode, exportImage, getCy, fitToVisibleArea })

// Watch for data changes
watch([() => props.nodes, () => props.edges], () => {
  buildGraph()
}, { deep: true })

watch(() => props.hiddenTypes, () => {}, { deep: true })

watch(() => props.selectedNodeId, (id) => {
  if (id) focusNode(id)
  else { selectedNode = null; connectedIds.clear(); highlightedNodeId = null }
})

// When panel opens/closes, refit nodes to visible area
watch(() => props.panelOpen, () => {
  setTimeout(() => fitToVisibleArea(), 50)
})

onMounted(() => {
  nextTick(() => {
    resize()
    buildGraph()
    lastTime = performance.now() * 0.001
    animFrame = requestAnimationFrame(animate)
    canvasRef.value?.addEventListener('mousemove', onMouseMove)
    canvasRef.value?.addEventListener('click', onClick)
    window.addEventListener('resize', () => { resize(); buildGraph() })
    emit('ready')
  })
})

onBeforeUnmount(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  canvasRef.value?.removeEventListener('mousemove', onMouseMove)
  canvasRef.value?.removeEventListener('click', onClick)
})
</script>
